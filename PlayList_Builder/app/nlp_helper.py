# app/nlp_helper.py
# -------------------------------------------------------------------
# Lightweight NLP utilities with safe fallbacks (no hard crash if
# spaCy or the en_core_web_sm model aren't installed).
# -------------------------------------------------------------------

from __future__ import annotations

from typing import List, Tuple

try:
    import spacy  # type: ignore
except Exception:
    spacy = None  # graceful fallback

from app.llm_helper import generate_playlist_description

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
MOODS: List[str] = ["happy", "sad", "energetic", "chill", "focus", "romantic", "angry", "calm"]
ACTIVITIES: List[str] = ["workout", "study", "party", "relax", "commute", "sleep"]


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
    Heuristically detect mood and context/activity from user text.
    Returns: (mood, context) strings
    - mood defaults to 'neutral' if none found
    - context defaults to 'none' if none found
    """
    t = (text or "").lower()
    detected_mood = next((m for m in MOODS if m in t), "neutral")
    detected_context = next((c for c in ACTIVITIES if c in t), "none")
    return detected_mood, detected_context


def summarize_playlist(tracks: list, user_text: str = "") -> str:
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
    "summarize_playlist",
    "MOODS",
    "ACTIVITIES",
]
