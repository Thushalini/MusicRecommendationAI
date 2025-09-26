# app/fastapi_agents.py

import numpy as np
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query

from .schemas import RecommendRequest, RecommendResponse, Candidate, TelemetryEvent
from . import datastore as ds, profiles as prof, candidates as cands, scoring, ranking
from .spotify import ingest_user_library

app = FastAPI(title="User Preference Manager")

# Spotify auth routes
from .spotify_auth import router as spotify_router
app.include_router(spotify_router)

# ----------------- utility routes -----------------
@app.post("/spotify/sync/{user_id}")
def spotify_sync(user_id: str):
    try:
        out = ingest_user_library(user_id)
        prof.rebuild_user_profile(user_id)
        return {"user_id": user_id, "ingest": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health")
def health():
    return {"ok": True}

# ----------------- telemetry -----------------
@app.post("/telemetry")
def telemetry(ev: TelemetryEvent):
    e = ev.dict()
    if not e.get("ts"):
        e["ts"] = datetime.now(timezone.utc).isoformat()
    ds.ensure_user(e["user_id"])
    ds.log_interaction(e)

    vecs = ds.fetch_track_vectors([e["track_id"]])
    tv = vecs.get(e["track_id"])
    if tv is not None:
        prof.update_profile_online(e["user_id"], tv)

    prof.rebuild_user_profile(e["user_id"])
    return {"status": "logged"}

# ----------------- profile -----------------
@app.get("/profile/{user_id}")
def profile(user_id: str):
    p = ds.get_user_profile(user_id)
    if not p:
        ds.ensure_user(user_id)
        p = prof.rebuild_user_profile(user_id)
        return {"user_id": user_id, "long_term_vec_norm": float(np.linalg.norm(p["long_term_vec"]))}
    return {"user_id": user_id, "last_updated": p["last_updated"]}

# ----------------- recommend -----------------
@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    user_id = req.user_id
    ds.ensure_user(user_id)

    # Ensure profile exists
    p = ds.get_user_profile(user_id)
    if not p or p.get("long_term_vec") is None:
        p = prof.rebuild_user_profile(user_id)

    user_vec_raw = p["long_term_vec"]
    user_vec = (
        np.array(user_vec_raw, dtype=float)
        if not isinstance(user_vec_raw, str)
        else np.fromstring(user_vec_raw.strip("[]"), sep=",", dtype=float)
    )

    # Bootstrap from top tracks if zero vector
    if np.linalg.norm(user_vec) < 1e-6:
        try:
            from .spotify import get_top, get_audio_features
            tops = get_top(user_id, type_="tracks", time_range="short_term", limit=20)
            t_ids = [t["id"] for t in tops if t]
            af = get_audio_features(user_id, t_ids)
            vecs = []
            for tid in t_ids:
                a = af.get(tid)
                if not a:
                    continue
                base = np.array(
                    [
                        a.get("danceability") or 0.0,
                        a.get("energy") or 0.0,
                        a.get("valence") or 0.0,
                        (a.get("tempo") or 0.0) / 250.0,
                        a.get("acousticness") or 0.0,
                        a.get("instrumentalness") or 0.0,
                        a.get("liveness") or 0.0,
                        a.get("speechiness") or 0.0,
                    ],
                    dtype=float,
                )
                base = base / (np.linalg.norm(base) + 1e-8)
                vecs.append(base)
            if vecs:
                m = np.mean(np.vstack(vecs), axis=0)
                user_vec = m / (np.linalg.norm(m) + 1e-8)
        except Exception:
            pass

    need = req.need or None
    need_genre = need.genre if need else None
    artist_ids = need.artists if (need and need.artists) else None

    pool = max(req.k * 10, 200)
    cand_list = cands.get_candidates(user_vec, need_genre, pool=pool, artist_ids=artist_ids)

    if not cand_list:
        return RecommendResponse(
            user_id=user_id,
            candidates=[],
            explanations={"note": ["no candidates found; try Sync Library and remove filters"]},
        )

    cand_vecs = np.vstack([np.array(c["vec"], dtype=float) for c in cand_list])
    session_vec = np.zeros_like(user_vec)
    scores = scoring.score(user_vec=user_vec, session_vec=session_vec, cand_vecs=cand_vecs)
    idxs = ranking.mmr(cand_list, scores, topk=req.k, artist_cap=2)
    final = [Candidate(track_id=cand_list[i]["track_id"], score=float(scores[i])) for i in idxs]

    return RecommendResponse(
        user_id=user_id,
        candidates=final,
        explanations={
            "top_signals": ["long_term", "genre_filter" if need_genre else "", "artist_filter" if artist_ids else ""],
            "pool": [str(len(cand_list))],
        },
    )

# ----------------- search -----------------
@app.get("/search")
def search(q: str = Query(..., min_length=2), limit: int = 25):
    rows = ds.search_tracks_by_name(q, limit=limit)
    return {"results": rows}
