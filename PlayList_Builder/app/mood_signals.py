from __future__ import annotations
from typing import Dict, Tuple, Any
from app.mood_quiz_algo import compute_mood_from_quiz

MOODS = ["happy","chill","angry","sad","workout","sleep"]

def softmax_norm(scores: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(v,0.0) for v in scores.values()) or 1.0
    return {k: max(v,0.0)/s for k,v in scores.items()}

def sam_to_mood(valence: float, arousal: float) -> Dict[str, float]:
    """valence, arousal in [0,1] → soft weights over MOODS."""
    out = {m:0.0 for m in MOODS}
    if valence >= 0.6 and arousal >= 0.6:
        out["happy"] = 0.6; out["workout"] = 0.4
    elif valence >= 0.6 and arousal < 0.6:
        out["chill"] = 0.7; out["happy"] = 0.3
    elif valence < 0.6 and arousal >= 0.6:
        out["angry"] = 0.7; out["workout"] = 0.3
    else:
        out["sad"] = 0.6; out["sleep"] = 0.4
    return out


# --- RG 10-Q QUIZ (primary) ----------------------------------------------------
def rg_quiz_signal(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Input payload: {"quiz": {"q1".."q9": "SA|A|CS|D|SD", "q10": "yes|no"}}
    Returns:
      {
        "final": {"label","x","y","confidence","method":"quiz_rg"},
        "dist":  {mood: weight, ...}  # normalized
      }
    """
    q = (payload or {}).get("quiz") or {}
    answers = {i: q.get(f"q{i}") for i in range(1, 10)}
    q10 = q.get("q10")
    focus_yes = True if str(q10).lower() in {"y","yes","true","1"} else False if q10 is not None else None

    final = compute_mood_from_quiz(answers, focus_yes)  # label,x,y,confidence,method

    # Convert (x,y) to a soft MOODS distribution
    dist = sam_to_mood(final.get("x", 0.5), final.get("y", 0.5))

    # If label is one of our MOODS, give it a small boost before normalizing
    lbl = final.get("label")
    if lbl in dist:
        dist[lbl] = dist.get(lbl, 0.0) + 0.15

    return {
        "final": final,
        "dist": softmax_norm(dist),
    }
