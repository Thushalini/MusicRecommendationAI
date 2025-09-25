# app/mood_detector.py
from __future__ import annotations
import os, re, joblib
from typing import Dict, Tuple

import logging; log = logging.getLogger("mood")

_MODEL = None
MODEL_PATH = os.getenv("MOOD_MODEL_PATH", "models/mood_tfidf.joblib")

try:
    if os.path.exists(MODEL_PATH):
        _MODEL = joblib.load(MODEL_PATH)
        log.info(f"[mood] ML model loaded ✅ -> {MODEL_PATH} | labels={_MODEL['labels']}")
    else:
        log.warning(f"[mood] No model file at {MODEL_PATH}; using lexicon fallback.")
except Exception as e:
    _MODEL = None
    log.exception(f"[mood] Failed to load model ({MODEL_PATH}); using lexicon fallback. {e}")

# Lightweight lexicon fallback
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
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if t]

# Try to load model
_pipeline = _classes = None
try:
    obj = joblib.load(MODEL_PATH)
    _pipeline = obj["pipeline"]
    _classes = obj["classes"]
except Exception:
    _pipeline = None
    _classes = None

def _lexicon_detect(text: str) -> Tuple[str, float, Dict[str, int]]:
    toks = _normalize(text)
    scores = {m: 0 for m in MOOD_LEXICON}
    for m, vocab in MOOD_LEXICON.items():
        for t in toks:
            if t in vocab:
                scores[m] += 1
    best_mood, best_score = "chill", 0
    for m, sc in scores.items():
        if sc > best_score:
            best_mood, best_score = m, sc
    conf = 0.15 if best_score == 0 else min(0.95, 0.45 + 0.1 * best_score)
    return best_mood, conf, scores

def detect_mood(text: str) -> Tuple[str, float, Dict[str, float]]:
    # Model path: prefer ML model if available
    if _pipeline is not None and _classes is not None:
        probs = _pipeline.predict_proba([text])[0]
        idx = int(probs.argmax())
        mood = str(_classes[idx])
        conf = float(probs[idx])
        # If the model is unsure, fall back to lexicon
        if conf < 0.45:
            return _lexicon_detect(text)
        # provide per-class scores for debugging
        return mood, conf, {str(c): float(p) for c, p in zip(_classes, probs)}
    # Fallback: lexicon
    return _lexicon_detect(text)
