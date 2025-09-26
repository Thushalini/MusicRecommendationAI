# app/ranking.py
import numpy as np
from numpy.linalg import norm
from typing import List, Dict

def _cos(a, b): return float(np.dot(a,b) / ((norm(a)*norm(b)) + 1e-8))

def mmr(cands: List[Dict], base: np.ndarray, lambda_=0.7, topk=50, artist_cap=2) -> List[int]:
    selected, remaining = [], list(range(len(cands)))
    artist_counts = {}
    while remaining and len(selected) < topk:
        best_i, best_val = None, -1e9
        for i in remaining:
            div = 0.0 if not selected else max(_cos(cands[i]["vec"], cands[j]["vec"]) for j in selected)
            val = lambda_*base[i] - (1-lambda_)*div
            art = cands[i].get("artist_id")
            if art and artist_counts.get(art,0) >= artist_cap: val -= 1.0
            if val > best_val: best_i, best_val = i, val
        selected.append(best_i)
        art = cands[best_i].get("artist_id")
        if art: artist_counts[art] = artist_counts.get(art,0) + 1
        remaining.remove(best_i)
    return selected
