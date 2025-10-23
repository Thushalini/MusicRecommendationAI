from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional, Any

import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

log = logging.getLogger("genre")
if not log.handlers:
    logging.basicConfig(level=logging.INFO)

# -------------------------------------------------
# Model location (override with GENRE_MODEL_PATH)
# -------------------------------------------------
MODEL_PATH = Path(os.getenv("GENRE_MODEL_PATH", "app/models/genre_classifier.joblib")).resolve()
DATASET_PATH = Path(os.getenv("GENRE_DATASET_PATH", "app/data/genre_dataset.csv")).resolve()

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
# Try to load Genre Classification model
# -------------------------------------------------
_PIPELINE: Optional[Any] = None
_GENRE_CLASSES: Optional[list[str]] = None
_MOOD_ENCODER: Optional[LabelEncoder] = None

if _HAS_JOBLIB and _HAS_SKLEARN and MODEL_PATH.exists():
    try:
        obj = joblib.load(MODEL_PATH)
        if isinstance(obj, dict):
            _PIPELINE = obj.get("pipeline", None) or None
            _genre_classes = obj.get("genre_classes", None)
            _GENRE_CLASSES = [str(c) for c in _genre_classes] if _genre_classes is not None else None
            _MOOD_ENCODER = obj.get("mood_encoder", None) or None
        else:
            _PIPELINE = obj
            _GENRE_CLASSES = [str(c) for c in getattr(_PIPELINE, "classes_", [])] or None
            # If pipeline is directly loaded, we might not have mood_encoder
            # This needs to be handled carefully or retrained if missing.
            log.warning("[genre] Mood encoder not found in direct pipeline load. Retraining might be needed.")

        if _PIPELINE is not None and _GENRE_CLASSES is not None and _MOOD_ENCODER is not None:
            log.info("[genre] ML model loaded ✅ -> %s", MODEL_PATH)
        else:
            log.warning("[genre] Model object missing pipeline, genre classes or mood encoder. Retraining might be needed.")
            _PIPELINE = None
            _GENRE_CLASSES = None
            _MOOD_ENCODER = None
    except Exception as e:
        _PIPELINE = None
        _GENRE_CLASSES = None
        _MOOD_ENCODER = None
        log.warning("[genre] Failed to load model (%s); retraining might be needed. %s", MODEL_PATH, e)
else:
    if not MODEL_PATH.exists():
        log.info("[genre] No model file at %s; training new model.", MODEL_PATH)
    elif not _HAS_SKLEARN:
        log.info("[genre] scikit-learn not installed; skipping model load and training.")
    elif not _HAS_JOBLIB:
        log.info("[genre] joblib not installed; skipping model load and training.")

def _normalize_text(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return " ".join([tok for tok in t.split() if tok])

def train_genre_classifier(
    dataset_path: Path = DATASET_PATH,
    model_output_path: Path = MODEL_PATH
) -> Tuple[Any, list[str], LabelEncoder]:
    """
    Trains a genre classification model using text and mood features.
    """
    if not _HAS_SKLEARN or not _HAS_JOBLIB:
        log.error("scikit-learn or joblib not installed. Cannot train genre classifier.")
        raise ImportError("scikit-learn and joblib are required for genre classification.")

    log.info("Loading genre dataset from %s", dataset_path)
    df = pd.read_csv(dataset_path)
    df["text"] = df["text"].apply(_normalize_text)

    # Encode moods
    mood_encoder = LabelEncoder()
    df["mood_encoded"] = mood_encoder.fit_transform(df["mood"])

    # Create a combined feature for text and mood
    # We'll concatenate the normalized text with the encoded mood as a string
    # This allows TF-IDF to pick up on mood-related "tokens"
    df["combined_features"] = df["text"] + " mood_" + df["mood"].str.lower()

    X = df["combined_features"]
    y = df["genre"]

    log.info("Training genre classification pipeline...")
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(stop_words='english', max_features=5000)),
        ('classifier', LogisticRegression(max_iter=1000, solver='liblinear'))
    ])
    pipeline.fit(X, y)

    genre_classes = list(pipeline.classes_)
    log.info("Genre classification model trained with classes: %s", genre_classes)

    # Save the pipeline, genre classes, and mood encoder
    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "pipeline": pipeline,
        "genre_classes": genre_classes,
        "mood_encoder": mood_encoder
    }, model_output_path)
    log.info("Genre classification model saved to %s", model_output_path)

    global _PIPELINE, _GENRE_CLASSES, _MOOD_ENCODER
    _PIPELINE = pipeline
    _GENRE_CLASSES = genre_classes
    _MOOD_ENCODER = mood_encoder

    return pipeline, genre_classes, mood_encoder

# Train model if not already loaded
if _PIPELINE is None:
    try:
        train_genre_classifier()
    except Exception as e:
        log.error("Failed to train genre classifier on startup: %s", e)

def classify_genre(text: str, detected_mood: str) -> Tuple[str, float, Dict[str, float]]:
    """
    Classifies the genre based on input text and a detected mood.
    Returns: (genre_label, confidence, per_class_scores)
    """
    if _PIPELINE is None or _GENRE_CLASSES is None or _MOOD_ENCODER is None:
        log.error("Genre classification model not loaded or trained.")
        return "unknown", 0.0, {}

    normalized_text = _normalize_text(text)
    # Ensure detected_mood is in the encoder's classes, if not, use a fallback or retrain
    if detected_mood not in _MOOD_ENCODER.classes_:
        log.warning("Detected mood '%s' not in trained mood classes. Using 'unknown' or first available mood.", detected_mood)
        # Fallback to a known mood or handle as an unknown category
        # For simplicity, we'll just use the provided mood as a string token
        # and rely on TF-IDF to handle it, but a more robust solution might
        # involve re-training or a default mood.
        mood_token = detected_mood.lower()
    else:
        mood_token = detected_mood.lower()

    combined_input = normalized_text + " mood_" + mood_token

    try:
        probs = _PIPELINE.predict_proba([combined_input])[0]
        idx = int(probs.argmax())
        genre = str(_GENRE_CLASSES[idx])
        conf = float(probs[idx])
        return genre, conf, {str(c): float(p) for c, p in zip(_GENRE_CLASSES, probs)}
    except Exception as e:
        log.error("Error during genre classification: %s", e)
        return "unknown", 0.0, {}
