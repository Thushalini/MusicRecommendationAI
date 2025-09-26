# app/candidates.py

import numpy as np
from typing import Dict, List, Optional
from . import datastore as ds

def get_candidates(
    user_vec: np.ndarray,
    need_genre: Optional[str],
    pool: int = 500,
    artist_ids: Optional[List[str]] = None,
) -> List[Dict]:
    rows = ds.ann_by_user_vector(user_vec, pool=pool, genre=need_genre, artist_ids=artist_ids)
    cands: List[Dict] = []
    for r in rows:
        vec = r["vec"]
        if isinstance(vec, str):
            arr = np.fromstring(vec.strip("[]"), sep=",", dtype=float)
        else:
            arr = np.array(vec, dtype=float)
        cands.append(
            {
                "track_id": r["track_id"],
                "artist_id": r["artist_id"],
                "genres": r["genres"] or [],
                "vec": arr,
            }
        )
    return cands
