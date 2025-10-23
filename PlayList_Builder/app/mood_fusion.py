from __future__ import annotations
from typing import Dict, Tuple, List

MOODS: List[str] = ["happy", "chill", "angry", "sad", "workout", "sleep", "calm"]

def _ensure_all_moods(d: Dict[str, float]) -> Dict[str, float]:
    out = {m: 0.0 for m in MOODS}
    for k, v in (d or {}).items():
        if k in out:
            out[k] = float(v)
    s = sum(out.values()) or 1.0
    return {k: v / s for k, v in out.items()}

def fuse_mood(
    text_scores: Dict[str, float],
    rg_quiz_scores: Dict[str, float] | None = None,
    w_text: float = 0.7,
    w_rg_quiz: float = 0.3,
) -> Tuple[str, float, Dict[str, float]]:
    """
    Fuse mood using only:
      - text_scores: scores from free-text analysis
      - rg_quiz_scores: scores from the RG mood quiz (optional)

    Weights default to 70% text, 30% quiz. Adjust via w_text / w_rg_quiz.
    """
    # Normalize/complete
    ts = _ensure_all_moods(text_scores)
    qs = _ensure_all_moods(rg_quiz_scores or {})

    # Weighted sum (only text + RG quiz)
    fused = {m: w_text * ts[m] + w_rg_quiz * qs[m] for m in MOODS}

    # Normalize
    total = sum(fused.values()) or 1.0
    fused = {k: v / total for k, v in fused.items()}

    label = max(fused, key=fused.get)
    conf = fused[label]
    return label, conf, fused
