# app/mood_quiz_algo.py
from __future__ import annotations
from typing import Dict, Tuple, Optional, List

# --- Q1..Q9 Likert options (SA,A,CS,D,SD) mapped to (valence X, energy Y)
# NOTE: Fill/adjust using the paper's table if you have it open.
# The pairs below are consistent with the sample in the paper and the Musynq chart ranges [0..1].
# Q10 is handled separately (focus override).
# Keys: question index (1..9) → option → (X,Y)

WEIGHTS: Dict[int, Dict[str, Tuple[float, float]]] = {
    1: {"SA": (0.0, 0.0), "A": (0.25, 0.25), "CS": (0.5, 0.5), "D": (0.375, 0.375), "SD": (0.5, 0.5)},
    2: {"SA": (0.0, 0.0), "A": (0.25, 0.25), "CS": (0.5, 0.5), "D": (0.375, 0.375), "SD": (0.5, 0.5)},
    3: {"SA": (0.0, 0.0), "A": (0.25, 0.25), "CS": (0.5, 0.5), "D": (0.75, 0.75), "SD": (0.875, 0.875)},
    4: {"SA": (1.0, 1.0), "A": (0.75, 0.75), "CS": (0.5, 0.5), "D": (0.25, 0.25), "SD": (0.0, 0.0)},
    5: {"SA": (1.0, 1.0), "A": (0.75, 0.75), "CS": (0.5, 0.5), "D": (0.25, 0.25), "SD": (0.0, 0.0)},
    6: {"SA": (1.0, 1.0), "A": (0.75, 0.75), "CS": (0.5, 0.5), "D": (0.25, 0.25), "SD": (0.0, 0.0)},
    # 7 mixes anger/sad/happy; paper sample shows D→(0.5,1) i.e., high energy, mid valence
    7: {"SA": (0.1, 1.0), "A": (0.25, 1.0), "CS": (0.5, 0.5), "D": (0.5, 1.0), "SD": (0.75, 0.75)},
    # 8 relaxed/sad; sample shows A→(0.5,0) (mid valence, very low energy)
    8: {"SA": (0.75, 0.0), "A": (0.5, 0.0), "CS": (0.5, 0.5), "D": (0.25, 0.25), "SD": (0.0, 0.0)},
    # 9 anger/relaxed (irritability); treat SA/A as high energy, low valence
    9: {"SA": (0.0, 1.0), "A": (0.25, 1.0), "CS": (0.5, 0.5), "D": (0.6, 0.4), "SD": (0.8, 0.2)},
}
LIKERT = ["SA", "A", "CS", "D", "SD"]

def _ema(vals: List[float], alpha: float = 0.5) -> float:
    if not vals: return 0.5
    ema = vals[0]
    for v in vals[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema

def quadrant_to_label(x: float, y: float) -> str:
    # Musynq: origin shifted to (0.5,0.5). Quadrants define mood. (Paper)
    # I: Happy, II: Anger, III: Sad, IV: Relaxed
    dx, dy = x - 0.5, y - 0.5
    if dx >= 0 and dy >= 0:  # QI
        return "happy"
    if dx < 0 and dy >= 0:   # QII
        return "angry"
    if dx < 0 and dy < 0:    # QIII
        return "sad"
    return "relaxed"         # QIV

def compute_mood_from_quiz(answers: Dict[int, str], focus_yes: Optional[bool]) -> Dict:
    """
    answers: {1..9: "SA"|"A"|"CS"|"D"|"SD"} ; "CS" excluded from averaging (paper).
    focus_yes: Q10 Yes/No (True/False/None) → if True, override to 'focus'
    Returns: {"label", "x", "y", "confidence", "method": "quiz_rg"}
    """
    xs, ys = [], []
    xs_all, ys_all = [], []

    for q in range(1, 10):
        opt = answers.get(q)
        if opt not in LIKERT: continue
        x, y = WEIGHTS[q][opt]
        xs_all.append(x); ys_all.append(y)
        if opt != "CS":  # exclude "Can't Say" from simple average
            xs.append(x); ys.append(y)

    if not xs: xs = xs_all or [0.5]
    if not ys: ys = ys_all or [0.5]

    x_avg = sum(xs) / len(xs)
    y_avg = sum(ys) / len(ys)

    x_ema = _ema(xs_all or xs)
    y_ema = _ema(ys_all or ys)

    x_final = (x_avg + x_ema) / 2.0
    y_final = (y_avg + y_ema) / 2.0

    if focus_yes is True:
        return {"label": "focus", "x": x_final, "y": y_final, "confidence": 0.9, "method": "quiz_rg"}

    label = quadrant_to_label(x_final, y_final)
    # crude confidence: distance from center
    import math
    conf = min(0.99, 0.5 + min(0.5, math.hypot(x_final - 0.5, y_final - 0.5)))
    return {"label": label, "x": x_final, "y": y_final, "confidence": round(conf, 3), "method": "quiz_rg"}
