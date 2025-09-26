# app/profiles.py
import numpy as np, math
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any, DefaultDict 
from . import datastore as ds

BASE_WEIGHTS = {"play_end":1.0, "like":3.0, "add_to_playlist":2.0, "skip":-2.0}
TAU_DAYS = 21.0

def _decay(delta_days: float) -> float:
    return math.exp(-delta_days / TAU_DAYS)

def _parse_vec(raw) -> np.ndarray:
    if isinstance(raw, str):  # '[0.1,0.2,...]'
        return np.fromstring(raw.strip("[]"), sep=",", dtype=float)
    return np.array(raw, dtype=float)

def _now_utc() -> np.datetime64:
    return np.datetime64('now', 's')

def rebuild_user_profile(user_id: str) -> Dict[str, Any]:
    events = ds.fetch_recent_user_events(user_id, limit=2000)
    dim = int(ds.VECTOR_DIM)

    if not events:
        long_vec = np.zeros(dim, dtype=float)
        ds.upsert_user_profile(user_id, long_vec, {}, {})
        return {"user_id": user_id, "long_term_vec": long_vec, "genre_counts": {}, "mood_counts": {}}

    # fetch track vectors (should return dict[id] -> np.ndarray)
    tids = [e["track_id"] for e in events if e.get("track_id")]
    track_vecs = ds.fetch_track_vectors(tids) or {}

    numer = np.zeros(dim, dtype=float)
    denom = 1e-8
    genre_counts: DefaultDict[str, float] = defaultdict(float)

    now = _now_utc().astype("datetime64[s]")

    for e in events:
        tid = e.get("track_id")
        if not tid:
            continue
        ts = np.datetime64(e["ts"]).astype("datetime64[s]") if e.get("ts") else now
        delta_days = max(float((now - ts) / np.timedelta64(1, 'D')), 0.0)

        w = dict(BASE_WEIGHTS).get(e.get("event", ""), 0.0) * _decay(delta_days)
        if e.get("skipped"): w -= 2.0
        if e.get("liked"): w += 1.0

        vec = track_vecs.get(tid)
        if vec is None:
            continue
        vec = np.array(vec, dtype=float)
        nv = np.linalg.norm(vec)
        if nv > 0:
            vec = vec / nv

        numer += w * vec
        denom += abs(w)

        # TODO: if ds can return genres per track, increment genre_counts here

    long_vec = numer / denom
    n = np.linalg.norm(long_vec)
    if n > 0:
        long_vec = long_vec / n
    else:
        long_vec = np.zeros(dim, dtype=float)

    ds.upsert_user_profile(user_id, long_vec, dict(genre_counts), {})
    return {"user_id": user_id, "long_term_vec": long_vec, "genre_counts": dict(genre_counts)}


def update_profile_online(user_id: str, track_vec):
    # pull current profile
    p = ds.get_user_profile(user_id)
    dim = int(ds.VECTOR_DIM)
    if not p or p["long_term_vec"] is None:
        long_vec = np.zeros(dim, dtype=float)
        count = 0.0
    else:
        vtxt = p["long_term_vec"]
        long_vec = np.fromstring(vtxt.strip("[]"), sep=",", dtype=float) if isinstance(vtxt,str) else np.array(vtxt, dtype=float)
        count = 1.0

    alpha = 0.05  # small learning rate
    new_vec = (1 - alpha) * long_vec + alpha * track_vec
    new_vec = new_vec / (np.linalg.norm(new_vec) + 1e-8)
    ds.upsert_user_profile(user_id, new_vec, {}, {})
    return new_vec

def mood_label(valence, energy):
    if valence is None or energy is None: return None
    if valence > 0.6 and energy > 0.6: return "happy"
    if valence < 0.4 and energy < 0.4: return "sad"
    if energy > 0.6: return "energetic"
    if energy < 0.4: return "chill"
    return "neutral"
