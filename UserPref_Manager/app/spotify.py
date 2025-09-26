# app/spotify.py  
import time, os, requests, psycopg
from typing import Dict, List, Set
from .datastore import upsert_artist, upsert_track, ensure_user, VECTOR_DIM
from dotenv import load_dotenv; load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

def _get_tokens(user_id):
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT access_token, refresh_token, expires_at FROM user_tokens WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        if not row: raise RuntimeError("User not authorized")
        return dict(access=row[0], refresh=row[1], exp=row[2])

def _refresh(user_id, refresh_token):
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    data = {"grant_type":"refresh_token","refresh_token":refresh_token,
            "client_id": os.getenv("SPOTIFY_CLIENT_ID"),"client_secret": os.getenv("SPOTIFY_CLIENT_SECRET")}
    r = requests.post(TOKEN_URL, data=data); r.raise_for_status()
    j = r.json()
    access = j["access_token"]; exp = int(time.time()) + int(j.get("expires_in",3600))
    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("UPDATE user_tokens SET access_token=%s, expires_at=%s WHERE user_id=%s",
                    (access, exp, user_id))
    return access

def _auth_header(token): return {"Authorization": f"Bearer {token}"}
def _authed_token(user_id):
    t = _get_tokens(user_id)
    if t["exp"] - int(time.time()) < 60:
        t["access"] = _refresh(user_id, t["refresh"])
    return t["access"]

def get_saved_tracks(user_id, limit=50, max_pages=20) -> List[dict]:
    token = _authed_token(user_id)
    url = "https://api.spotify.com/v1/me/tracks"
    items, params = [], {"limit": limit}
    for _ in range(max_pages):
        r = requests.get(url, headers=_auth_header(token), params=params); r.raise_for_status()
        j = r.json()
        items += j.get("items", [])
        if not j.get("next"): break
        url = j["next"]; params = None
    return items

def get_recently_played(user_id, limit=50, after_ms=None) -> List[dict]:
    token = _authed_token(user_id)
    url = "https://api.spotify.com/v1/me/player/recently-played"
    params = {"limit": limit}
    if after_ms: params["after"] = int(after_ms)
    r = requests.get(url, headers=_auth_header(token), params=params); r.raise_for_status()
    return r.json().get("items", [])

def get_top(user_id, type_="tracks", time_range="medium_term", limit=50) -> List[dict]:
    token = _authed_token(user_id)
    url = f"https://api.spotify.com/v1/me/top/{type_}"
    params = {"time_range": time_range, "limit": limit}
    r = requests.get(url, headers=_auth_header(token), params=params); r.raise_for_status()
    return r.json().get("items", [])

def get_audio_features(user_id, track_ids: List[str]) -> Dict[str, dict]:
    token = _authed_token(user_id)
    out = {}
    for i in range(0, len(track_ids), 100):
        chunk = track_ids[i:i+100]
        url = "https://api.spotify.com/v1/audio-features"
        r = requests.get(url, headers=_auth_header(token), params={"ids": ",".join(chunk)})
        r.raise_for_status()
        for a in r.json().get("audio_features", []):
            if a: out[a["id"]] = a
    return out

def get_artists(user_id, artist_ids: List[str]) -> Dict[str, dict]:
    token = _authed_token(user_id)
    out = {}
    for i in range(0, len(artist_ids), 50):
        chunk = artist_ids[i:i+50]
        url = "https://api.spotify.com/v1/artists"
        r = requests.get(url, headers=_auth_header(token), params={"ids": ",".join(chunk)})
        r.raise_for_status()
        for a in r.json().get("artists", []):
            out[a["id"]] = a
    return out

def _base_vec_from_audio(a: dict):
    import numpy as np
    v = np.array([
        (a.get("danceability") or 0.0),
        (a.get("energy") or 0.0),
        (a.get("valence") or 0.0),
        ((a.get("tempo") or 0.0)/250.0),
        (a.get("acousticness") or 0.0),
        (a.get("instrumentalness") or 0.0),
        (a.get("liveness") or 0.0),
        (a.get("speechiness") or 0.0),
    ], dtype=float)
    v = v / (np.linalg.norm(v) + 1e-8)
    vec = np.zeros(VECTOR_DIM, dtype=float); vec[:len(v)] = v
    return vec

def ingest_user_library(user_id: str):
    """Ingest saved, top (short/medium/long), and recently-played into DB."""
    ensure_user(user_id)

    # collect candidate tracks
    saved = get_saved_tracks(user_id)
    recent = get_recently_played(user_id, limit=50)
    top_short  = get_top(user_id, "tracks", "short_term", 50)
    top_medium = get_top(user_id, "tracks", "medium_term", 50)
    top_long   = get_top(user_id, "tracks", "long_term", 50)

    t_ids: List[str] = []
    a_ids: List[str] = []

    # saved
    t_ids += [it["track"]["id"] for it in saved if it.get("track")]
    for it in saved:
        tr = it.get("track")
        if tr and tr.get("artists"):
            a_ids += [a["id"] for a in tr["artists"]]

    # recent
    for it in recent:
        tr = it.get("track")
        if tr:
            t_ids.append(tr["id"])
            if tr.get("artists"): a_ids += [a["id"] for a in tr["artists"]]

    # tops
    for coll in (top_short, top_medium, top_long):
        for tr in coll:
            if tr:
                t_ids.append(tr["id"])
                if tr.get("artists"): a_ids += [a["id"] for a in tr["artists"]]

    # dedupe (preserve order)
    def _uniq(seq): 
        seen: Set[str] = set(); out=[]
        for x in seq:
            if x and x not in seen:
                seen.add(x); out.append(x)
        return out

    t_ids = _uniq(t_ids)
    a_ids = _uniq(a_ids)

    af = get_audio_features(user_id, t_ids) if t_ids else {}
    arts = get_artists(user_id, a_ids) if a_ids else {}

    # upserts
    for aid in a_ids:
        ad = arts.get(aid, {})
        upsert_artist({"artist_id": aid, "name": ad.get("name"), "genres": ad.get("genres", [])})

    for tid in t_ids:
        # we need a minimal track object—pull via audio features we already fetched
        a = af.get(tid, {})
        # NOTE: we still need basic track metadata (name/popularity/duration). Best-effort via Tracks API:
        try:
            token = _authed_token(user_id)
            meta = requests.get(f"https://api.spotify.com/v1/tracks/{tid}",
                                headers=_auth_header(token), timeout=8).json()
        except Exception:
            meta = {}

        vec = _base_vec_from_audio(a) if a else None
        audio_json = {
            "danceability": a.get("danceability"),
            "energy": a.get("energy"),
            "valence": a.get("valence"),
            "tempo": a.get("tempo"),
            "acousticness": a.get("acousticness"),
            "instrumentalness": a.get("instrumentalness"),
            "liveness": a.get("liveness"),
            "speechiness": a.get("speechiness"),
        } if a else {}

        first_artist = (meta.get("artists") or [{}])[0]
        artist_id = first_artist.get("id")
        artist_genres = (arts.get(artist_id, {}) or {}).get("genres", []) if artist_id else []

        upsert_track({
            "track_id": tid,
            "artist_id": artist_id,
            "name": meta.get("name"),
            "release_year": int(((meta.get("album") or {}).get("release_date") or "0000")[:4] or 0) if meta.get("album") else None,
            "duration_ms": meta.get("duration_ms"),
            "popularity": meta.get("popularity"),
            "audio_json": audio_json,
            "genres": artist_genres,
            "vec": vec if vec is not None else _base_vec_from_audio({"danceability":0,"energy":0,"valence":0,"tempo":0,"acousticness":0,"instrumentalness":0,"liveness":0,"speechiness":0})
        })

    return {
        "saved_tracks": len(saved),
        "recently_played": len(recent),
        "top_short": len(top_short),
        "top_medium": len(top_medium),
        "top_long": len(top_long),
        "unique_tracks_upserted": len(t_ids),
        "unique_artists_upserted": len(a_ids),
    }
