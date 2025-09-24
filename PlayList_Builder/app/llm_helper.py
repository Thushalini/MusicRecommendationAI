# app/llm_helper.py
# ---------------------------------------------------------------------------
# OpenAI helper (playlist descriptions) + lightweight genre classifier.
# Mood detection is delegated to app.agents.mood_detector to keep a single
# source of truth. We keep a thin wrapper here for backward compatibility.
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
# Playlist description (LLM, with safe fallback)
# ---------------------------------------------------------------------------
def generate_playlist_description(mood: str, context: str, tracks: List[Dict[str, Any]]) -> str:
    mood = (mood or "").strip() or "mixed"
    context = (context or "").strip() or "general"

    sample_lines = []
    for t in tracks[:12]:
        name = (t.get("name") or "").strip()
        artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
        if name:
            sample_lines.append(f"- {name}" + (f" — {artists}" if artists else ""))
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

    if not OPENAI_API_KEY or _client is None:
        return f"A {mood} playlist tailored for {context}. Smooth flow and consistent vibe curated from the selected tracks."

    try:
        if _use_new_sdk:
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
        return f"A {mood} playlist tailored for {context}. A cohesive flow that matches the requested vibe."


# ---------------------------------------------------------------------------
# Mood detection (proxy to agent for single source of truth)
# ---------------------------------------------------------------------------
from app.mood_detector import detect_mood as _detect_mood_agent

def detect_mood(text: str) -> Tuple[str, float]:
    """
    Back-compat wrapper: returns (mood, confidence).
    Internally uses app.agents.mood_detector.detect_mood which returns
    (mood, confidence, scores).
    """
    mood, conf, _ = _detect_mood_agent(text or "")
    return mood, float(conf)


# ---------------------------------------------------------------------------
# Genre classifier (kept here)
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
    # languages (your builder handles these too)
    "sinhala": {"sinhala", "si", "sinhalese"},
    "tamil": {"tamil", "ta"},
    "hindi": {"hindi", "hi"},
    "english": {"english", "en"},
}

def classify_genre(text: str) -> Tuple[str, float]:
    t = (text or "").lower()
    if not t:
        return "pop", 0.3

    if "hip hop" in t or "hip-hop" in t:
        return "hip hop", 0.85
    if "r&b" in t or "rnb" in t or "r and b" in t:
        return "r&b", 0.85

    for canon, aliases in _GENRE_ALIASES.items():
        for a in aliases:
            if a in t:
                return canon, 0.75

    for canon in _GENRE_ALIASES.keys():
        if canon in t:
            return canon, 0.6

    return "pop", 0.35


__all__ = [
    "generate_playlist_description",
    "detect_mood",          # wrapper (2-tuple) for back-compat
    "classify_genre",
]
