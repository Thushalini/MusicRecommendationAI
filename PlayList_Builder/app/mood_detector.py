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
# -------------------------------------------------
MOOD_LEXICON: Dict[str, set[str]] = {
    "happy": {"happy","joy","excited","fun","party","energetic","dance","vibe","good","great","cheerful","uplift","smile"},
    "sad": {"sad","down","not happy","blue","depressed","cry","lonely","heartbroken","miss","nostalgic","slow","melancholy","exhausted"},
    "chill": {"chill","calm","relax","lofi","coffee","study","focus","mellow","soft","ambient","smooth","peaceful"},
    "angry": {"angry","mad","rage","furious","aggressive","metal","hard","scream"},
    "energetic": {"hype","pump","fast","high bpm","edm","electro","jump","power","workout"},
    "romantic": {"love","romance","date","valentine","kiss","crush","affection","couple","romantic","slow dance"},
    "workout": {"workout","gym","run","cardio","training","hiit","beast","motivation"},
    "sleep": {"sleep","bedtime","asleep","doze","night","lullaby","soothing","white","noise"}
}

def _normalize(text: str) -> list[str]:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return [tok for tok in t.split() if tok]

def _lexicon_detect(text: str) -> Tuple[str, float, Dict[str, int]]:
    toks = _normalize(text)
    scores = {m: 0 for m in MOOD_LEXICON}
    for mood, vocab in MOOD_LEXICON.items():
        for tok in toks:
            if tok in vocab:
                scores[mood] += 1
    best_mood, best_score = "chill", 0
    for m, sc in scores.items():
        if sc > best_score:
            best_mood, best_score = m, sc
    conf = 0.15 if best_score == 0 else min(0.95, 0.45 + 0.1 * best_score)
    return best_mood, conf, scores

# -------------------------------------------------
# Public API
#   Returns: (mood_label, confidence, per_class_scores)
# -------------------------------------------------
def detect_mood(text: str) -> Tuple[str, float, Dict[str, float]]:
    # Use ML model if available
    if _PIPELINE is not None:
        try:
            if hasattr(_PIPELINE, "predict_proba"):
                probs = _PIPELINE.predict_proba([text or ""])[0]
                classes = _CLASSES or [str(c) for c in getattr(_PIPELINE, "classes_", [])]
                if classes and len(classes) == len(probs):
                    idx = int(probs.argmax())
                    mood = str(classes[idx])
                    conf = float(probs[idx])
                    if conf < 0.45:
                        return _lexicon_detect(text)
                    return mood, conf, {str(c): float(p) for c, p in zip(classes, probs)}
            # Fallback to plain predict if no probas
            if hasattr(_PIPELINE, "predict"):
                pred = _PIPELINE.predict([text or ""])[0]
                mood = str(pred)
                # no calibrated proba → give a neutral confidence
                return mood, 0.6, {mood: 0.6}
        except Exception as e:
            log.warning("[mood] Model predict failed; fallback to lexicon. %s", e)

    # Lexicon fallback
    best_mood, conf, raw = _lexicon_detect(text)
    # convert counts to pseudo-scores (normalize to 0..1)
    total = max(raw.values()) or 1
    norm = {k: (v / total) for k, v in raw.items()}
    return best_mood, conf, norm
