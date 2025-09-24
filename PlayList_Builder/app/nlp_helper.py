# app/nlp_helper.py
# -------------------------------------------------------------------
# Lightweight NLP utilities with safe fallbacks (no hard crash if
# spaCy or the en_core_web_sm model aren't installed).
# Also integrates the Mood Detector agent for text → mood inference.
# -------------------------------------------------------------------

from __future__ import annotations
from typing import List, Tuple, Dict, Any

try:
    import spacy  # type: ignore
except Exception:
    spacy = None  # graceful fallback

from app.llm_helper import generate_playlist_description
from app.mood_detector import detect_mood, MOOD_LEXICON  
# -------------------------------------------------------------------
# Lazy spaCy loader (prevents import-time crashes)
# -------------------------------------------------------------------
_NLP = None

def _get_nlp():
    """
    Returns a spaCy Language object.
    - Tries to load 'en_core_web_sm'
    - If unavailable, returns a blank English pipeline (no NER)
    - If spaCy itself isn't installed, returns None
    """
    global _NLP
    if _NLP is not None:
        return _NLP

    if spacy is None:
        _NLP = None
        return _NLP

    try:
        _NLP = spacy.load("en_core_web_sm")
    except Exception:
        # Fallback: blank English (no NER). Still lets tokenization work.
        _NLP = spacy.blank("en")
    return _NLP


# -------------------------------------------------------------------
# Constants for heuristic detection
# -------------------------------------------------------------------
# Keep activities here (context like "workout", "study", etc.)
ACTIVITIES: List[str] = ["workout", "study", "party", "relax", "commute", "sleep", "focus"]

# Derive available moods from the agent’s lexicon (single source of truth)
MOODS: List[str] = sorted(list(MOOD_LEXICON.keys()))


# -------------------------------------------------------------------
# Public APIs
# -------------------------------------------------------------------
def extract_entities(text: str) -> List[Tuple[str, str]]:
    """
    Extract named entities from text using spaCy if available.
    Falls back to an empty list when NER isn't available.
    Returns: list of (entity_text, entity_label)
    """
    nlp = _get_nlp()
    if nlp is None or not hasattr(nlp, "pipe_names") or "ner" not in getattr(nlp, "pipe_names", []):
        # No spaCy or no NER component: return empty safely
        return []
    doc = nlp(text or "")
    return [(ent.text, ent.label_) for ent in doc.ents]


def detect_mood_and_context(text: str) -> Tuple[str, str]:
    """
    Detect mood using the Mood Detector agent and infer a coarse context/activity.
    Returns: (mood, context)
    - mood comes from agent (fallback handled inside agent)
    - context is keyword-based; defaults to 'none' if not found
    """
    mood, _conf, _scores = detect_mood(text or "")
    t = (text or "").lower()
    context = next((c for c in ACTIVITIES if c in t), "none")
    return mood, context


def detect_mood_with_confidence(text: str) -> Tuple[str, float, Dict[str, int]]:
    """
    Convenience passthrough to the agent for callers that need confidence/scores too.
    Returns: (mood, confidence, raw_scores)
    """
    return detect_mood(text or "")


def summarize_playlist(tracks: List[Dict[str, Any]], user_text: str = "") -> str:
    """
    Generate a summarized playlist description via LLM (with safe fallback
    inside generate_playlist_description).
    tracks: list of dicts with keys 'name' and 'artists' (list of {'name': ...})
    """
    mood, context = detect_mood_and_context(user_text)
    description = generate_playlist_description(
        mood=mood,
        context=context,
        tracks=tracks or [],
    )
    return description


__all__ = [
    "extract_entities",
    "detect_mood_and_context",
    "detect_mood_with_confidence",
    "summarize_playlist",
    "MOODS",
    "ACTIVITIES",
]
