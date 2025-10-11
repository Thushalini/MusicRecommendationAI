from __future__ import annotations
from typing import Dict, Tuple

MOODS = ["happy","chill","angry","sad","workout","sleep"]

# 1) Color → mood prior (normalize so they sum to 1)
COLOR_MAP: Dict[str, Dict[str, float]] = {
    "yellow": {"happy":0.7,"chill":0.2,"workout":0.1},
    "green":  {"chill":0.6,"happy":0.3,"sleep":0.1},
    "red":    {"angry":0.6,"workout":0.3,"happy":0.1},
    "blue":   {"sad":0.6,"chill":0.3,"sleep":0.1},
    "purple": {"sleep":0.4,"chill":0.4,"sad":0.2},
    "orange": {"happy":0.5,"workout":0.4,"chill":0.1},
    "black":  {"sad":0.5,"sleep":0.3,"angry":0.2},
    "white":  {"chill":0.5,"happy":0.3,"sleep":0.2},
}

# 2) Emoji → mood prior
EMOJI_MAP: Dict[str, Dict[str, float]] = {
    "😄":{"happy":0.8,"chill":0.2},
    "🙂":{"chill":0.6,"happy":0.4},
    "😠":{"angry":0.8,"workout":0.2},
    "😢":{"sad":0.9,"sleep":0.1},
    "💪":{"workout":0.85,"happy":0.15},
    "😴":{"sleep":0.9,"chill":0.1},
}

def softmax_norm(scores: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(v,0.0) for v in scores.values()) or 1.0
    return {k: max(v,0.0)/s for k,v in scores.items()}

def sam_to_mood(valence: float, arousal: float) -> Dict[str, float]:
    """
    valence, arousal in [0,1]. Quadrant logic with soft weights.
    """
    out = {m:0.0 for m in MOODS}
    if valence >= 0.6 and arousal >= 0.6:
        out["happy"] = 0.6; out["workout"] = 0.4
    elif valence >= 0.6 and arousal < 0.6:
        out["chill"] = 0.7; out["happy"] = 0.3
    elif valence < 0.6 and arousal >= 0.6:
        out["angry"] = 0.7; out["workout"] = 0.3
    else:
        # low V, low A
        out["sad"] = 0.6; out["sleep"] = 0.4
    return out

def color_signal(color_name: str) -> Dict[str,float]:
    base = COLOR_MAP.get(color_name.lower(), {"chill":0.34,"happy":0.33,"sleep":0.33})
    return softmax_norm(base)

def emoji_signal(emoji: str) -> Dict[str,float]:
    base = EMOJI_MAP.get(emoji, {"chill":0.34,"happy":0.33,"sleep":0.33})
    return softmax_norm(base)

def quiz_signal(answers: Dict[str, str]) -> Dict[str,float]:
    """
    Tiny 3Q quiz. answers = {"energy":"low|medium|high", "social":"solo|group",
                             "focus":"relax|party|gym|study"}
    """
    out = {m:0.0 for m in MOODS}
    energy = answers.get("energy","medium"); social = answers.get("social","solo")
    focus  = answers.get("focus","relax")

    if energy == "high": out["workout"] += 0.5; out["happy"] += 0.3
    if energy == "low":  out["sleep"]   += 0.5; out["sad"]   += 0.2
    if social == "group": out["happy"] += 0.3; out["workout"] += 0.2
    if social == "solo":  out["chill"] += 0.3; out["sad"] += 0.1

    if focus == "gym":   out["workout"] += 0.5
    elif focus == "party": out["happy"] += 0.5
    elif focus == "study": out["chill"] += 0.5
    else: # relax
        out["chill"] += 0.3; out["sleep"] += 0.2

    return softmax_norm(out)
