# app/user_pref_manager.py
from __future__ import annotations
import os, json, httpx, collections, itertools
import profile
from typing import Dict, Any, List, Tuple, Optional
import math
import re
import urllib.parse
import httpx

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
    artist_names = collections.Counter()
    genres     = collections.Counter()
    track_ids  = collections.Counter()
    moods      = collections.Counter()

    for pl in saved:
        # playlist-level mood (if present)
        req = pl.get("request") or {}
        mood = (req.get("mood") or "")
        if isinstance(mood, str) and mood.strip():
            moods[mood.strip().lower()] += 1

        for t in pl.get("tracks", []):
            # artist ids (if present)
            for a in t.get("artist_ids", []) or []:
                if a:
                    artist_ids[a] += 1
            # artist names
            for a_name in t.get("artists", []) or []:
                if isinstance(a_name, str) and a_name.strip():
                    artist_names[a_name.strip().lower()] += 1
            for g in t.get("genres", []) or []:
                if isinstance(g, str) and g.strip():
                    genres[g.lower()] += 1
            if tid := t.get("id"):
                track_ids[tid] += 1

    profile = {
        "top_artist_ids": [a for a,_ in artist_ids.most_common(5)],
        "top_artist_names": [a for a,_ in artist_names.most_common(5)],
        "top_genres":     [g for g,_ in genres.most_common(5)],
        "top_track_ids":  [t for t,_ in track_ids.most_common(5)],
        "top_moods":      [m for m,_ in moods.most_common(3)],
    }
    return profile

  

def _spotify_id_from_any(v: str) -> Optional[str]:
    """Extract a Spotify track/artist id from a plain id, spotify: URI or open.spotify.com URL."""
    if not v:
        return None
    s = str(v).strip()
    # spotify:track:<id>
    m = re.search(r"spotify:(?:track|artist):([A-Za-z0-9]+)", s)
    if m:
        return m.group(1)
    # open.spotify.com/track/<id>
    if "open.spotify.com" in s:
        try:
            p = urllib.parse.urlparse(s)
            parts = p.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] in ("track", "artist"):
                return parts[1].split("?")[0]
        except Exception:
            return None
    # if it already looks like an id (alphanumeric)
    if re.fullmatch(r"[A-Za-z0-9]{8,}", s):
        return s
    return None


async def spotify_recommendations(
    access_token: str,
    seeds: Dict[str, List[str]],
    limit: int = 30,
    market: str = "US",
) -> List[Dict[str, Any]]:
    if not access_token:
        return []

    headers = {"Authorization": f"Bearer {access_token}"}
    params: Dict[str, str] = {"limit": str(min(max(limit, 1), 100)), "market": market}

    # sanitize seeds -> ensure we send plain Spotify ids (not URIs or local ids)
    seed_tracks = [ _spotify_id_from_any(x) for x in (seeds.get("track_ids") or []) ]
    seed_tracks = [s for s in seed_tracks if s]
    seed_artists = [ _spotify_id_from_any(x) for x in (seeds.get("artist_ids") or []) ]
    seed_artists = [s for s in seed_artists if s]
    seed_genres = [g for g in (seeds.get("genres") or []) if isinstance(g, str) and g.strip()]

    # choose up to Spotify limits (up to 5 total seeds; prefer tracks)
    total_seed_slots = 5
    chosen = []
    if seed_tracks:
        use = seed_tracks[:3]
        params["seed_tracks"] = ",".join(use)
        chosen += use
    if seed_artists and len(chosen) < total_seed_slots:
        use = seed_artists[: total_seed_slots - len(chosen)]
        params["seed_artists"] = ",".join(use)
        chosen += use
    if seed_genres and len(chosen) < total_seed_slots:
        use = seed_genres[: total_seed_slots - len(chosen)]
        params["seed_genres"] = ",".join(use)
        chosen += use

    # If no valid seeds remain, bail out early (caller can fall back)
    if not chosen:
        return []

    # compute feature centroid (unchanged)...
    feature_keys = [
        "danceability", "energy", "valence",
        "acousticness", "instrumentalness", "speechiness", "liveness", "tempo"
    ]
    feature_centroid: Dict[str, float] = {}
    try:
        if seed_tracks:
            ids_q = ",".join(seed_tracks)
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    "https://api.spotify.com/v1/audio-features",
                    headers=headers,
                    params={"ids": ids_q},
                )
                r.raise_for_status()
                af_data = r.json().get("audio_features") or []
            feats = [f for f in af_data if isinstance(f, dict)]
            # compute centroid as before...
            rows = []
            for f in feats:
                if not f: 
                    continue
                row = {}
                for k in feature_keys:
                    v = f.get(k)
                    if v is None:
                        continue
                    row[k] = float(v) if k != "tempo" else float(v) / 200.0
                if row:
                    rows.append(row)
            if rows:
                centroid = {}
                for k in feature_keys:
                    vals = [r[k] for r in rows if k in r]
                    if vals:
                        centroid[k] = sum(vals) / len(vals)
                feature_centroid = centroid
    except httpx.HTTPStatusError:
        # Spotify returned HTTP error when fetching audio-features -> ignore features
        feature_centroid = {}
    except Exception:
        feature_centroid = {}

    if feature_centroid:
        for k, v in feature_centroid.items():
            if k == "tempo":
                try:
                    bpm = float(v) * 200.0
                    params[f"target_{k}"] = str(max(30.0, min(220.0, bpm)))
                except Exception:
                    pass
            else:
                params[f"target_{k}"] = str(max(0.0, min(1.0, float(v))))

    # finally call recommendations - catch spotify errors and return empty list (caller fallbacks)
    try:
        url = "https://api.spotify.com/v1/recommendations"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers=headers, params=params)
            r.raise_for_status()
            data = r.json() or {}
    except httpx.HTTPStatusError:
        # log if you want, then return empty so caller can fallback to local items
        return []
    except Exception:
        return []

    out = []
    for tr in data.get("tracks", []):
        out.append({
            "id": tr.get("id"),
            "name": tr.get("name"),
            "artists": [a.get("name") for a in tr.get("artists", [])],
            "artist_ids": [a.get("id") for a in tr.get("artists", [])],
            "album_img": (tr.get("album", {}).get("images") or [{}])[0].get("url"),
            "preview_url": tr.get("preview_url"),
            "uri": tr.get("uri"),
        })
    return out

async def recommend_for_you(access_token: str, limit: int = 30) -> Dict[str, Any]:
    # build profile and seeds as before...
    saved = _load_saved()
    profile = build_user_profile(saved)
    if not saved:
        return {"profile": profile, "recommendations": []}

    seeds = {
        "track_ids": profile.get("top_track_ids", []),
        "artist_ids": profile.get("top_artist_ids", []),
        "artist_names": profile.get("top_artist_names", []),
        "genres": profile.get("top_genres", []),
        "moods": profile.get("top_moods", []),
    }

    # try spotify but do not propagate Spotify HTTP errors — fallback to local
    if access_token and (seeds["track_ids"] or seeds["artist_ids"] or seeds["genres"]):
        try:
            recs = await spotify_recommendations(access_token, seeds, limit=limit)
            if recs:
                return {"profile": profile, "recommendations": recs}
        except Exception:
            # swallow and fall back
            pass

    # fallback: local resurfacing (unchanged)
    seen = set()
    candidates: List[Tuple[float,int,Dict[str,Any]]] = []
    order_idx = 0

    seed_track_set = set([_spotify_id_from_any(x) for x in (seeds.get("track_ids") or []) if x])
    seed_artist_id_set = set([_spotify_id_from_any(x) for x in (seeds.get("artist_ids") or []) if x])
    seed_artist_name_set = set([s.lower() for s in (seeds.get("artist_names") or []) if isinstance(s, str)])
    seed_genre_set = set([g.lower() for g in (seeds.get("genres") or []) if isinstance(g, str)])
    seed_mood_set = set([m.lower() for m in (seeds.get("moods") or []) if isinstance(m, str)])

    for pl_idx, pl in enumerate(reversed(saved)):
        pl_mood = ((pl.get("request") or {}).get("mood") or "").lower()
        for t in pl.get("tracks", []):
            tid = _spotify_id_from_any(t.get("id") or t.get("uri") or t.get("spotify_id"))
            if not tid:
                continue
            # avoid exact seed tracks
            if tid in seed_track_set:
                continue
            if tid in seen:
                continue
            seen.add(tid)

            score = 0.0
            # artist id match (strong)
            track_artist_ids = [ _spotify_id_from_any(a) for a in (t.get("artist_ids") or []) if a ]
            if any(a in seed_artist_id_set for a in track_artist_ids):
                score += 3.0
            # artist name match
            track_artist_names = [ (a or "").lower() for a in (t.get("artists") or []) if isinstance(a, str) ]
            if any(a in seed_artist_name_set for a in track_artist_names):
                score += 2.0
            # genre match
            track_genres = [ (g or "").lower() for g in (t.get("genres") or []) if isinstance(g, str) ]
            if any(g in seed_genre_set for g in track_genres):
                score += 2.0
            # playlist mood match
            if pl_mood and pl_mood in seed_mood_set:
                score += 1.5
            # fuzzy / heuristic: title contains a seed artist name
            for a in seed_artist_name_set:
                if a and any(a in (tn or "").lower() for tn in track_artist_names + [t.get("name","").lower()]):
                    score += 0.5
            # small recency boost (prefer more recent playlists)
            recency_boost = 1.0 / (1 + pl_idx)
            score += recency_boost * 0.1

            candidates.append((score, order_idx, {
                "id": tid,
                "name": t.get("name"),
                "artists": t.get("artists") or [],
                "album_img": (t.get("album_img") or "") if isinstance(t.get("album_img"), str) else "",
                "preview_url": t.get("preview_url"),
                "uri": t.get("spotify_url") or t.get("uri"),
                "score": score,
            }))
            order_idx += 1

    # sort candidates by score desc then by original order
    candidates.sort(key=lambda x: (-x[0], x[1]))
    out = [c[2] for c in candidates if c[0] > 0.0][:limit]

    # If we couldn't find any scored similar tracks, fall back to returning recent unique saved tracks (but avoid seeds)
    if not out:
        seen = set()
        out = []
        for pl in reversed(saved):
            for t in pl.get("tracks", []):
                tid = _spotify_id_from_any(t.get("id") or t.get("uri") or t.get("spotify_id"))
                if not tid or tid in seen or tid in seed_track_set:
                    continue
                seen.add(tid)
                out.append({
                    "id": tid,
                    "name": t.get("name"),
                    "artists": t.get("artists") or [],
                    "album_img": (t.get("album_img") or "") if isinstance(t.get("album_img"), str) else "",
                    "preview_url": t.get("preview_url"),
                    "uri": t.get("spotify_url") or t.get("uri"),
                })
                if len(out) >= limit:
                    break
            if len(out) >= limit:
                break
    return {"profile": profile, "recommendations": out}
            



# earlier version of spotify_recommendations (before sanitizing ids):
# async def spotify_recommendations(
#     access_token: str,
#     seeds: Dict[str, List[str]],
#     limit: int = 30,
#     market: str = "US",
# ) -> List[Dict[str, Any]]:
#     """
#     Hybrid content-based recommender:
#     - Prefer seed_tracks (up to 3) + seed_artists (up to 2) + seed_genres (up to 5),
#     - Fetch audio-features for the seed tracks, compute centroid of key features,
#       and pass them as target_* params to Spotify's recommendations endpoint.
#     """
#     if not access_token:
#         return []

#     headers = {"Authorization": f"Bearer {access_token}"}
#     params: Dict[str, str] = {"limit": str(min(max(limit, 1), 100)), "market": market}

#     # choose seeds (Spotify allows up to 5 seeds total)
#     seed_tracks = (seeds.get("track_ids") or [])[:3]
#     seed_artists = (seeds.get("artist_ids") or [])[:2]
#     seed_genres = (seeds.get("genres") or [])[:5]

#     # allocate remaining slots if fewer tracks/artists
#     total_seed_slots = 5
#     chosen = []
#     if seed_tracks:
#         params["seed_tracks"] = ",".join(seed_tracks)
#         chosen += seed_tracks
#     if seed_artists and len(chosen) < total_seed_slots:
#         params["seed_artists"] = ",".join(seed_artists[: total_seed_slots - len(chosen)])
#         chosen += seed_artists[: total_seed_slots - len(chosen)]
#     if seed_genres and len(chosen) < total_seed_slots:
#         params["seed_genres"] = ",".join(seed_genres[: total_seed_slots - len(chosen)])
#         chosen += seed_genres[: total_seed_slots - len(chosen)]

#     # If we have seed tracks, try to fetch audio features and compute centroid
#     feature_keys = [
#         "danceability", "energy", "valence",
#         "acousticness", "instrumentalness", "speechiness", "liveness", "tempo"
#     ]
#     feature_centroid: Dict[str, float] = {}
#     try:
#         if seed_tracks:
#             # spotify audio-features accepts up to 100 ids
#             ids_q = ",".join(seed_tracks)
#             async with httpx.AsyncClient(timeout=15) as client:
#                 r = await client.get(
#                     "https://api.spotify.com/v1/audio-features",
#                     headers=headers,
#                     params={"ids": ids_q},
#                 )
#                 r.raise_for_status()
#                 af_data = r.json().get("audio_features") or []
#             feats: List[Dict[str, Any]] = [f for f in af_data if isinstance(f, dict)]
#             if feats:
#                 # normalize tempo by a heuristic (divide by 200 to keep in 0..1 range)
#                 rows = []
#                 for f in feats:
#                     if f is None: continue
#                     row = {}
#                     for k in feature_keys:
#                         v = f.get(k)
#                         if v is None:
#                             continue
#                         if k == "tempo":
#                             # avoid extreme tempos
#                             row[k] = float(v) / 200.0
#                         else:
#                             row[k] = float(v)
#                     if row:
#                         rows.append(row)
#                 if rows:
#                     centroid: Dict[str, float] = {}
#                     for k in feature_keys:
#                         vals = [r[k] for r in rows if k in r]
#                         if vals:
#                             centroid[k] = sum(vals) / len(vals)
#                     feature_centroid = centroid
#     except Exception:
#         # swallow feature errors — we'll still call recommendations without targets
#         feature_centroid = {}

#     # Push target_* params if we computed a centroid
#     if feature_centroid:
#         # Map centroid into Spotify target params (they accept e.g. target_danceability)
#         for k, v in feature_centroid.items():
#             if k == "tempo":
#                 # re-expand tempo back to BPM scale (approx)
#                 try:
#                     bpm = float(v) * 200.0
#                     params[f"target_{k}"] = str(max(30.0, min(220.0, bpm)))
#                 except Exception:
#                     continue
#             else:
#                 # clamp 0..1
#                 params[f"target_{k}"] = str(max(0.0, min(1.0, float(v))))

#     # Finally call Spotify recommendations
#     url = "https://api.spotify.com/v1/recommendations"
#     async with httpx.AsyncClient(timeout=20) as client:
#         r = await client.get(url, headers=headers, params=params)
#         r.raise_for_status()
#         data = r.json() or {}

#     out = []
#     for tr in data.get("tracks", []):
#         out.append({
#             "id": tr.get("id"),
#             "name": tr.get("name"),
#             "artists": [a.get("name") for a in tr.get("artists", [])],
#             "artist_ids": [a.get("id") for a in tr.get("artists", [])],
#             "album_img": (tr.get("album", {}).get("images") or [{}])[0].get("url"),
#             "preview_url": tr.get("preview_url"),
#             "uri": tr.get("uri"),
#         })
#     return out

# async def recommend_for_you(access_token: str, limit: int = 30) -> Dict[str, Any]:
#     """
#     Build a simple profile from saved playlists and return recommendations.
#     If an access_token is provided, use Spotify's recommendation API with content-targeting.
#     Otherwise fall back to resurfacing local saved favorites.
#     """
#     saved = _load_saved()
#     profile = build_user_profile(saved)

#     # If no saved data, return an empty profile
#     if not saved:
#         return {"profile": profile, "recommendations": []}

#     seeds = {
#         "track_ids": profile.get("top_track_ids", []),
#         "artist_ids": profile.get("top_artist_ids", []),
#         "genres": profile.get("top_genres", []),
#     }

#     # If we have a token and seeds, try the Spotify-based hybrid recommender
#     if access_token and (seeds["track_ids"] or seeds["artist_ids"] or seeds["genres"]):
#         try:
#             recs = await spotify_recommendations(access_token, seeds, limit=limit)
#             # If Spotify returned lots of tracks, return them
#             if recs:
#                 return {"profile": profile, "recommendations": recs}
#         except httpx.HTTPStatusError as e:
#             # Log at caller; fall through to local fallback
#             raise
#         # Fallback: surface saved tracks (reshuffle & dedupe) — local-only mode
#     seen = set()
#     out = []
#     for pl in reversed(saved):
#         for t in pl.get("tracks", []):
#             tid = t.get("id")
#             if not tid or tid in seen:
#                 continue
#             seen.add(tid)
#             out.append({
#                 "id": tid,
#                 "name": t.get("name"),
#                 "artists": t.get("artists") or [],
#                 "album_img": (t.get("album_img") or "") if isinstance(t.get("album_img"), str) else "",
#                 "preview_url": t.get("preview_url"),
#                 "uri": t.get("spotify_url") or t.get("uri"),
#             })
#             if len(out) >= limit:
#                 break
#         if len(out) >= limit:
#             break

#     return {"profile": profile, "recommendations": out}