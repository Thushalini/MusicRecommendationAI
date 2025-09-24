from typing import Dict, Any, Tuple, Optional

# -------------------------------------------------------------------
# Mood/context → target feature heuristics
# (kept compatible with your earlier draft)
# -------------------------------------------------------------------
def mood_targets(mood: str, context: Optional[str] = None) -> Dict[str, float | Tuple[float, float]]:
    """
    Returns a dict of target features or bounds based on mood and optional context.
    Keys may include: target_valence, target_energy, min_energy, max_energy,
    min_tempo, max_tempo, min_danceability, max_danceability, min_instrumentalness, ...
    """
    mood = (mood or "").lower().strip()
    context = (context or "").lower().strip()

    targets = {
        "happy":     {"target_valence": 0.85, "min_energy": 0.6},
        "sad":       {"target_valence": 0.25, "max_energy": 0.5},
        "energetic": {"target_valence": 0.7,  "min_energy": 0.8},
        "chill":     {"target_valence": 0.6,  "max_energy": 0.55, "max_tempo": 110},
        "focus":     {"max_energy": 0.55, "max_valence": 0.7, "min_instrumentalness": 0.2},
        "romantic":  {"target_valence": 0.7, "max_energy": 0.7},
        "angry":     {"min_energy": 0.85},
        "calm":      {"max_energy": 0.45, "max_tempo": 100},
    }.get(mood, {"target_valence": 0.7})

    # Context adjustments
    if context == "workout":
        targets.update({"min_energy": 0.8, "min_tempo": 120})
    elif context == "study":
        targets.update({"max_energy": 0.55, "max_tempo": 110})
    elif context == "party":
        targets.update({"min_energy": 0.75, "min_danceability": 0.7})
    elif context == "sleep":
        targets.update({"max_energy": 0.35, "max_tempo": 90})

    return targets


# -------------------------------------------------------------------
# Distance-based scorer
# Higher score = better match to targets
# -------------------------------------------------------------------
def score_tracks(
    target_vec: Dict[str, float | Tuple[float, float]],
    feats: Dict[str, Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """
    Compute a simple distance-based score for each track id given its feature dict.
    feats: {track_id: {"valence": .., "energy": .., "tempo": .., "danceability": .., "instrumentalness": ..}}
    """
    weights = weights or {
        "valence": 1.0,
        "energy": 1.2,
        "tempo": 0.6,
        "danceability": 0.6,
        "instrumentalness": 0.4,
    }

    scores: Dict[str, float] = {}

    target_valence = target_vec.get("target_valence", None)
    target_energy = target_vec.get("target_energy", None)

    for tid, f in feats.items():
        d = 0.0

        # Pull-to-target terms
        if target_valence is not None and f.get("valence") is not None:
            d += weights["valence"] * abs(float(f["valence"]) - float(target_valence))

        if target_energy is not None and f.get("energy") is not None:
            d += weights["energy"] * abs(float(f["energy"]) - float(target_energy))

        # Min/max constraints become penalties if violated
        if "min_tempo" in target_vec and f.get("tempo") is not None and float(f["tempo"]) < float(target_vec["min_tempo"]):
            d += weights["tempo"] * (float(target_vec["min_tempo"]) - float(f["tempo"])) / 200.0

        if "max_tempo" in target_vec and f.get("tempo") is not None and float(f["tempo"]) > float(target_vec["max_tempo"]):
            d += weights["tempo"] * (float(f["tempo"]) - float(target_vec["max_tempo"])) / 200.0

        if "min_energy" in target_vec and f.get("energy") is not None and float(f["energy"]) < float(target_vec["min_energy"]):
            d += weights["energy"] * (float(target_vec["min_energy"]) - float(f["energy"]))

        if "max_energy" in target_vec and f.get("energy") is not None and float(f["energy"]) > float(target_vec["max_energy"]):
            d += weights["energy"] * (float(f["energy"]) - float(target_vec["max_energy"]))

        if "min_danceability" in target_vec and f.get("danceability") is not None and float(f["danceability"]) < float(target_vec["min_danceability"]):
            d += weights["danceability"] * (float(target_vec["min_danceability"]) - float(f["danceability"]))

        if "min_instrumentalness" in target_vec and f.get("instrumentalness") is not None and float(f["instrumentalness"]) < float(target_vec["min_instrumentalness"]):
            d += weights["instrumentalness"] * (float(target_vec["min_instrumentalness"]) - float(f["instrumentalness"]))

        # Convert distance → score (bounded 0..1)
        scores[tid] = 1.0 / (1.0 + d)

    return scores


# -------------------------------------------------------------------
# Human-readable “why this track” string
# -------------------------------------------------------------------
def reason_string(f: Dict[str, Any]) -> str:
    """
    Build a compact reason string from audio features, e.g.:
    'energy=0.68, valence=0.31, danceability=0.55, tempo=92'
    """
    parts = []
    if f.get("energy") is not None:
        parts.append(f"energy={float(f['energy']):.2f}")
    if f.get("valence") is not None:
        parts.append(f"valence={float(f['valence']):.2f}")
    if f.get("danceability") is not None:
        parts.append(f"danceability={float(f['danceability']):.2f}")
    if f.get("tempo") is not None:
        parts.append(f"tempo={int(float(f['tempo']))}")
    return ", ".join(parts) if parts else "features unavailable"
