from __future__ import annotations
from typing import Dict, Tuple, List

MOODS = ["happy","chill","angry","sad","workout","sleep", "calm"]

def _ensure_all_moods(d: Dict[str,float]) -> Dict[str,float]:
    out = {m: 0.0 for m in MOODS}
    for k,v in d.items():
        if k in out: out[k] = float(v)
    s = sum(out.values()) or 1.0
    return {k:v/s for k,v in out.items()}

def fuse_mood(
    text_scores: Dict[str,float],
    color_scores: Dict[str,float] | None = None,
    emoji_scores: Dict[str,float] | None = None,
    sam_scores: Dict[str,float] | None = None,
    quiz_scores: Dict[str,float] | None = None,
    w_text: float = 0.6, w_color: float = 0.1, w_emoji: float = 0.15,
    w_sam: float = 0.1, w_quiz: float = 0.05
) -> Tuple[str, float, Dict[str,float]]:
    # Normalize/complete
    ts  = _ensure_all_moods(text_scores)
    cs  = _ensure_all_moods(color_scores or {})
    es  = _ensure_all_moods(emoji_scores or {})
    sams = _ensure_all_moods(sam_scores or {})
    qs  = _ensure_all_moods(quiz_scores or {})

    # Weighted sum
    fused = {m: w_text*ts[m] + w_color*cs[m] + w_emoji*es[m] + w_sam*sams[m] + w_quiz*qs[m] for m in MOODS}
    # Normalize
    s = sum(fused.values()) or 1.0
    fused = {k:v/s for k,v in fused.items()}

    label = max(fused, key=fused.get)
    conf  = fused[label]
    return label, conf, fused
