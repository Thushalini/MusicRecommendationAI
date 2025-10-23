# app/mood_detector.py
from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional, Any

log = logging.getLogger("mood")
if not log.handlers:
    logging.basicConfig(level=logging.INFO)

# -------------------------------------------------
# Model location (override with MOOD_MODEL_PATH)
# -------------------------------------------------
MODEL_PATH = Path(os.getenv("MOOD_MODEL_PATH", "app/models/mood_tfidf.joblib")).resolve()

# -------------------------------------------------
# Optional deps (we avoid loading if sklearn missing)
# -------------------------------------------------
try:
    import joblib  # type: ignore
    _HAS_JOBLIB = True
except Exception:
    _HAS_JOBLIB = False

try:
    import sklearn  # type: ignore  # noqa: F401
    _HAS_SKLEARN = True
except Exception:
    _HAS_SKLEARN = False

# -------------------------------------------------
# Try to load TF-IDF model (only if sklearn present)
# Supports:
#   - dict {"pipeline": <sklearn-pipeline>, "classes": [...]}
#   - direct sklearn pipeline with predict_proba / classes_
# -------------------------------------------------
_PIPELINE: Optional[Any] = None
_CLASSES: Optional[list[str]] = None

if _HAS_JOBLIB and _HAS_SKLEARN and MODEL_PATH.exists():
    try:
        obj = joblib.load(MODEL_PATH)
        if isinstance(obj, dict):
            _PIPELINE = obj.get("pipeline", None) or None
            _classes = obj.get("classes", None)
            _CLASSES = [str(c) for c in _classes] if _classes is not None else None
        else:
            _PIPELINE = obj
            _CLASSES = [str(c) for c in getattr(_PIPELINE, "classes_", [])] or None

        if _PIPELINE is not None:
            log.info("[mood] ML model loaded ✅ -> %s", MODEL_PATH)
        else:
            log.warning("[mood] Model object missing pipeline; using lexicon fallback.")
    except Exception as e:
        _PIPELINE = None
        _CLASSES = None
        log.warning("[mood] Failed to load model (%s); using lexicon fallback. %s", MODEL_PATH, e)
else:
    if not MODEL_PATH.exists():
        log.info("[mood] No model file at %s; using lexicon fallback.", MODEL_PATH)
    elif not _HAS_SKLEARN:
        log.info("[mood] scikit-learn not installed; skipping model load and using lexicon fallback.")
    elif not _HAS_JOBLIB:
        log.info("[mood] joblib not installed; using lexicon fallback.")

# -------------------------------------------------
# Lightweight lexicon fallback
# (keep labels minimal; you can extend if needed)
# -------------------------------------------------
MOOD_LEXICON: Dict[str, set[str]] = {
    "happy":   {"happy","joy","excited","fun","party","energetic","dance","vibe","good","great","cheerful","uplift","smile"},
    "sad":     {"sad","down","blue","depressed","cry","lonely","heartbroken","miss","nostalgic","slow","melancholy","exhausted"},
    "chill":   {"chill","calm","relax","lofi","coffee","study","focus","mellow","soft","ambient","smooth","peaceful"},
    "angry":   {"angry","mad","rage","furious","aggressive","scream"},
    "workout": {"workout","gym","run","cardio","training","hiit","beast","motivation","pump","power"},
    "sleep":   {"sleep","bedtime","asleep","doze","night","lullaby","soothing","white","noise"},
    # Optional extra:
    "calm":    {"calm","serene","soothing","gentle","quiet","tranquil"},
}

def _normalize(text: str) -> list[str]:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return [tok for tok in t.split() if tok]

def _lexicon_detect(text: str) -> Tuple[str, float, Dict[str, float]]:
    toks = _normalize(text)
    raw_counts = {m: 0 for m in MOOD_LEXICON}
    for mood, vocab in MOOD_LEXICON.items():
        for tok in toks:
            if tok in vocab:
                raw_counts[mood] += 1
    # best
    best_mood, best_score = "chill", 0
    for m, sc in raw_counts.items():
        if sc > best_score:
            best_mood, best_score = m, sc
    conf = 0.15 if best_score == 0 else min(0.95, 0.45 + 0.1 * best_score)
    # normalize to 0..1 distribution (avoid div0)
    denom = sum(raw_counts.values()) or 1
    probs = {k: (v / denom) for k, v in raw_counts.items()}
    # Ensure at least the winning mood reflects confidence floor
    if probs.get(best_mood, 0.0) < 0.15:
        probs[best_mood] = max(probs.get(best_mood, 0.0), 0.15)
    # renormalize
    s = sum(probs.values()) or 1.0
    probs = {k: v/s for k, v in probs.items()}
    return best_mood, conf, probs

# -------------------------------------------------
# Helpers for fusion with RG quiz
# -------------------------------------------------
def _complete_moods(d: Dict[str, float], all_labels: set[str]) -> Dict[str, float]:
    out = {m: 0.0 for m in all_labels}
    for k, v in (d or {}).items():
        if k in out:
            out[k] = float(v)
        else:
            # allow unseen moods from quiz to enter label set
            out[k] = float(v)
    # re-normalize
    s = sum(out.values()) or 1.0
    return {k: (v / s) for k, v in out.items()}

def _fuse_scores(text_scores: Dict[str, float],
                 quiz_scores: Optional[Dict[str, float]],
                 w_text: float,
                 w_quiz: float) -> Dict[str, float]:
    # union label space (supports quiz introducing labels like "calm")
    labels = set(text_scores.keys())
    if quiz_scores:
        labels |= set(quiz_scores.keys())
    if not labels:
        labels = set(MOOD_LEXICON.keys())

    t = _complete_moods(text_scores, labels)
    q = _complete_moods(quiz_scores or {}, labels)

    fused = {m: (w_text * t.get(m, 0.0) + w_quiz * q.get(m, 0.0)) for m in labels}
    s = sum(fused.values()) or 1.0
    return {k: v / s for k, v in fused.items()}

# -------------------------------------------------
# Public API
#   Only **text** and **rg_quiz** are used for mood detection.
#   Others are intentionally ignored per requirement.
#   Returns: (mood_label, confidence, per_class_scores)
# -------------------------------------------------
def detect_mood(
    text: str,
    rg_quiz_scores: Optional[Dict[str, float]] = None,
    w_text: float = 0.7,
    w_quiz: float = 0.3
) -> Tuple[str, float, Dict[str, float]]:
    """
    Detect mood using ONLY:
      - Free text (ML model if available → else lexicon)
      - RG quiz scores (already a dict of mood→score)
    Fusion: weighted average over shared label space (default 0.7/0.3).
    """
    # ---------- text → scores ----------
    text_probs: Dict[str, float] = {}

    if _PIPELINE is not None:
        try:
            if hasattr(_PIPELINE, "predict_proba"):
                probs = _PIPELINE.predict_proba([text or ""])[0]
                classes = _CLASSES or [str(c) for c in getattr(_PIPELINE, "classes_", [])]
                if classes and len(classes) == len(probs):
                    text_probs = {str(c): float(p) for c, p in zip(classes, probs)}
                else:
                    # fallback to predict only
                    if hasattr(_PIPELINE, "predict"):
                        pred = str(_PIPELINE.predict([text or ""])[0])
                        text_probs = {pred: 1.0}
            elif hasattr(_PIPELINE, "predict"):
                pred = str(_PIPELINE.predict([text or ""])[0])
                text_probs = {pred: 1.0}
        except Exception as e:
            log.warning("[mood] Model predict failed; fallback to lexicon. %s", e)

    if not text_probs:
        # lexicon fallback returns normalized dict
        _, _, text_probs = _lexicon_detect(text)

    # ---------- fuse with RG quiz ONLY ----------
    fused = _fuse_scores(text_probs, rg_quiz_scores, w_text=w_text, w_quiz=w_quiz)

    # choose best + confidence
    best_mood = max(fused, key=fused.get)
    confidence = float(fused[best_mood])

    return best_mood, confidence, fused
