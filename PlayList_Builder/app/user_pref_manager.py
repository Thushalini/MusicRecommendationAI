# app/user_pref_manager.py
from __future__ import annotations
import os, json, httpx, collections, itertools
from typing import Dict, Any, List, Tuple

SAVED_PATH = os.getenv("SAVED_PLAYLISTS_PATH", os.path.join(os.getcwd(), ".appdata", "saved_playlists.json"))

def _load_saved(path: str = SAVED_PATH) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # expected shape: [{"name": "...","tracks":[{"id":"...","name":"...","artists":["..."],
    # "artist_ids":["..."],"genres":["pop","dance"],"album_img":"..."}], "meta":{...}}, ...]
    return data if isinstance(data, list) else []

def build_user_profile(saved: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Lightweight profile from saved playlists."""
    artist_ids = collections.Counter()
    genres     = collections.Counter()
    track_ids  = collections.Counter()

    for pl in saved:
        for t in pl.get("tracks", []):
            for a in t.get("artist_ids", []) or []:
                artist_ids[a] += 1
            for g in t.get("genres", []) or []:
                genres[g.lower()] += 1
            if tid := t.get("id"):
                track_ids[tid] += 1

    profile = {
        "top_artist_ids": [a for a,_ in artist_ids.most_common(5)],
        "top_genres":     [g for g,_ in genres.most_common(5)],
        "top_track_ids":  [t for t,_ in track_ids.most_common(5)],
    }
    return profile

async def spotify_recommendations(
    access_token: str,
    seeds: Dict[str, List[str]],
    limit: int = 30,
    market: str = "US",
) -> List[Dict[str, Any]]:
    params = {
        "limit": str(limit),
        "market": market,
    }
    # Spotify allows up to 5 seeds total; prioritize tracks, then artists, then genres
    seed_tracks = seeds.get("track_ids", [])[:3]
    seed_artists = seeds.get("artist_ids", [])[:2]
    if not seed_tracks and not seed_artists:
        seed_genres = seeds.get("genres", [])[:5]
    else:
        seed_genres = []
    if seed_tracks: params["seed_tracks"] = ",".join(seed_tracks)
    if seed_artists: params["seed_artists"] = ",".join(seed_artists)
    if seed_genres: params["seed_genres"] = ",".join(seed_genres)

    url = "https://api.spotify.com/v1/recommendations"
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()

    out = []
    for tr in data.get("tracks", []):
        out.append({
            "id": tr["id"],
            "name": tr["name"],
            "artists": [a["name"] for a in tr.get("artists", [])],
            "artist_ids": [a["id"] for a in tr.get("artists", [])],
            "album_img": (tr.get("album", {}).get("images") or [{}])[0].get("url"),
            "preview_url": tr.get("preview_url"),
            "uri": tr.get("uri"),
        })
    return out

async def recommend_for_you(access_token: str, limit: int = 30) -> Dict[str, Any]:
    saved = _load_saved()
    profile = build_user_profile(saved)
    seeds = {
        "track_ids": profile["top_track_ids"],
        "artist_ids": profile["top_artist_ids"],
        "genres": profile["top_genres"],
    }
    recs = await spotify_recommendations(access_token, seeds, limit=limit)
    return {"profile": profile, "recommendations": recs}
