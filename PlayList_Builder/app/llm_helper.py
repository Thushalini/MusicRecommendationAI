# app/llm_helper.py
# ---------------------------------------------------------------------------
# OpenAI helper (with safe fallbacks) + lightweight mood/genre detectors
# This file is imported by:
#   - Streamlit UI (optional: playlist description)
#   - FastAPI stubs (/mood, /genre, /analyze) expecting detect_mood/classify_genre
# ---------------------------------------------------------------------------

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple, Dict, Any

from dotenv import load_dotenv

# Load .env from project root (.. from app/)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Try to support BOTH the legacy openai SDK and the new >=1.0 SDK
_client = None
_use_new_sdk = False
try:
    # New SDK style (openai>=1.0)
    from openai import OpenAI  # type: ignore
    if OPENAI_API_KEY:
        _client = OpenAI(api_key=OPENAI_API_KEY)
        _use_new_sdk = True
except Exception:
    pass

if not _client:
    try:
        # Legacy SDK style (openai<1.0)
        import openai  # type: ignore
        if OPENAI_API_KEY:
            openai.api_key = OPENAI_API_KEY
            _client = openai
            _use_new_sdk = False
    except Exception:
        _client = None


# ---------------------------------------------------------------------------
# Public: generate_playlist_description
# ---------------------------------------------------------------------------
def generate_playlist_description(mood: str, context: str, tracks: List[Dict[str, Any]]) -> str:
    """
    Returns a short 1–3 sentence human-readable description for the playlist.
    Safe fallback if OpenAI key is missing or request fails.
    """
    mood = (mood or "").strip() or "mixed"
    context = (context or "").strip() or "general"
    # Build a compact track list for the prompt
    sample_lines = []
    for t in tracks[:12]:  # cap prompt size
        name = (t.get("name") or "").strip()
        artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
        if name:
            if artists:
                sample_lines.append(f"- {name} — {artists}")
            else:
                sample_lines.append(f"- {name}")
    sample = "\n".join(sample_lines) if sample_lines else "- (tracks omitted)"

    prompt = (
        "Write a short description (1–3 sentences) of a Spotify-style playlist for a user.\n"
        "Constraints: be vivid but concise, no emojis, no hashtags, no repeated words, no title casing.\n"
        f"Mood: {mood}\n"
        f"Context: {context}\n"
        "Tracks (subset):\n"
        f"{sample}\n"
        "Now output only the description."
    )

    # Fallback (no key or no SDK)
    if not OPENAI_API_KEY or _client is None:
        return f"A {mood} playlist tailored for {context}. Smooth flow and consistent vibe curated from the selected tracks."

    try:
        if _use_new_sdk:
            # New SDK
            res = _client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "You are a concise, tasteful music copywriter."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=120,
            )
            txt = (res.choices[0].message.content or "").strip()
            return txt or f"A {mood} playlist for {context}."
        else:
            # Legacy SDK
            res = _client.ChatCompletion.create(
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": "You are a concise, tasteful music copywriter."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=120,
            )
            txt = (res["choices"][0]["message"]["content"] or "").strip()
            return txt or f"A {mood} playlist for {context}."
    except Exception:
        # Always return something
        return f"A {mood} playlist tailored for {context}. A cohesive flow that matches the requested vibe."
    

# ---------------------------------------------------------------------------
# Public: detect_mood  (used by FastAPI /mood and /analyze)
# ---------------------------------------------------------------------------
_MOOD_ORDER = ["happy", "sad", "energetic", "chill", "focus", "romantic", "angry", "calm"]
# simple keyword lists (extendable)
_MOOD_HINTS = {
    "happy":      ["happy", "joy", "smile", "feel good", "uplift", "bright"],
    "sad":        ["sad", "blue", "cry", "melancholy", "down"],
    "energetic":  ["energetic", "hype", "high energy", "pump", "power"],
    "chill":      ["chill", "laid back", "mellow", "chilled"],
    "focus":      ["focus", "study", "concentration", "deep work"],
    "romantic":   ["romantic", "love", "date", "valentine"],
    "angry":      ["angry", "rage", "aggressive"],
    "calm":       ["calm", "soothing", "relaxing", "ambient"],
}

def detect_mood(text: str) -> Tuple[str, float]:
    """
    Heuristic mood detector.
    Returns (mood, confidence 0..1). Defaults to 'chill' with low confidence.
    """
    t = (text or "").lower()
    if not t:
        return "chill", 0.3
    for mood in _MOOD_ORDER:
        for kw in _MOOD_HINTS[mood]:
            if kw in t:
                return mood, 0.8
    # fallbacks: look for explicit labels
    for mood in _MOOD_ORDER:
        if mood in t:
            return mood, 0.7
    return "chill", 0.4


# ---------------------------------------------------------------------------
# Public: classify_genre  (used by FastAPI /genre and /analyze)
# ---------------------------------------------------------------------------
_GENRE_ALIASES = {
    "hip hop": {"hip hop", "hip-hop", "rap"},
    "r&b": {"r&b", "rnb", "r and b"},
    "lofi": {"lofi", "lo-fi", "lo fi", "lowfi"},
    "edm": {"edm", "electronic", "dance"},
    "k-pop": {"k-pop", "kpop"},
    "j-pop": {"j-pop", "jpop"},
    "pop": {"pop"},
    "rock": {"rock", "alt rock", "alternative"},
    "indie": {"indie", "indie pop", "indie rock"},
    "classical": {"classical", "orchestral"},
    "jazz": {"jazz"},
    # allow languages typed as "genres" (your builder also handles these)
    "sinhala": {"sinhala", "si", "sinhalese"},
    "tamil": {"tamil", "ta"},
    "hindi": {"hindi", "hi"},
    "english": {"english", "en"},
}

def _canon_genre(s: str) -> str | None:
    s = (s or "").strip().lower()
    for canon, aliases in _GENRE_ALIASES.items():
        if s == canon or s in aliases:
            return canon
    return None

def classify_genre(text: str) -> Tuple[str, float]:
    """
    Heuristic genre classifier.
    Returns (canonical_genre_or_language, confidence 0..1). Defaults to 'pop'.
    """
    t = (text or "").lower()
    if not t:
        return "pop", 0.3

    # prefer multi-word patterns first
    if "hip hop" in t or "hip-hop" in t:
        return "hip hop", 0.85
    if "r&b" in t or "rnb" in t or "r and b" in t:
        return "r&b", 0.85

    # try aliases
    for canon, aliases in _GENRE_ALIASES.items():
        for a in aliases:
            if a in t:
                return canon, 0.75

    # last-gasp: any known canon term
    for canon in _GENRE_ALIASES.keys():
        if canon in t:
            return canon, 0.6

    return "pop", 0.35
