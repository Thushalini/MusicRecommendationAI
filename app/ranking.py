from typing import Dict, Any, List, Tuple
import numpy as np

def mood_targets(mood: str, context: str | None) -> Dict[str, float | Tuple[float,float]]:
    # ranges are heuristics—tweak during evaluation
    targets = {
        "happy":     {"target_valence": 0.85, "min_energy": 0.6},
        "sad":       {"target_valence": 0.25, "max_energy": 0.5},
        "energetic": {"target_valence": 0.7,  "min_energy": 0.8},
        "chill":     {"target_valence": 0.6,  "max_energy": 0.55, "max_tempo": 110},
        "focus":     {"max_energy": 0.55, "max_valence": 0.7, "min_instrumentalness": 0.2},
        "romantic":  {"target_valence": 0.7, "max_energy": 0.7},
        "angry":     {"min_energy": 0.85},
        "calm":      {"max_energy": 0.45, "max_tempo": 100}
    }.get(mood, {"target_valence": 0.7})

    if context == "workout":
        targets.update({"min_energy": 0.8, "min_tempo": 120})
    elif context == "study":
        targets.update({"max_energy": 0.55, "max_tempo": 110})
    elif context == "party":
        targets.update({"min_energy": 0.75, "min_danceability": 0.7})
    elif context == "sleep":
        targets.update({"max_energy": 0.35, "max_tempo": 90})
    return targets

def score_tracks(target_vec: Dict[str, float | Tuple[float,float]],
                 feats: Dict[str, Dict[str, Any]],
                 weights: Dict[str, float] | None = None) -> Dict[str, float]:
    # Convert to a simple distance score; smaller distance → higher score
    weights = weights or {
        "valence": 1.0, "energy": 1.2, "tempo": 0.6, "danceability": 0.6, "instrumentalness": 0.4
    }
    scores = {}
    # Pull target points if defined
    target_valence = target_vec.get("target_valence", None)
    target_energy  = target_vec.get("target_energy", None)
    for tid, f in feats.items():
        d = 0.0
        if target_valence is not None and f.get("valence") is not None:
            d += weights["valence"] * abs(f["valence"] - target_valence)
        if target_energy is not None and f.get("energy") is not None:
            d += weights["energy"] * abs(f["energy"] - target_energy)
        if "min_tempo" in target_vec and f.get("tempo") is not None and f["tempo"] < target_vec["min_tempo"]:
            d += weights["tempo"] * (target_vec["min_tempo"] - f["tempo"]) / 200
        if "max_tempo" in target_vec and f.get("tempo") is not None and f["tempo"] > target_vec["max_tempo"]:
            d += weights["tempo"] * (f["tempo"] - target_vec["max_tempo"]) / 200
        # You can add more terms as needed…

        scores[tid] = 1.0 / (1.0 + d)  # higher is better
    return scores

def reason_string(f: Dict[str, Any]) -> str:
    parts = []
    for k in ["energy","valence","danceability","tempo"]:
        v = f.get(k)
        if v is None: 
            continue
        parts.append(f"{k}={v:.2f}" if k != "tempo" else f"tempo={int(v)}")
    return ", ".join(parts)
