from __future__ import annotations
import re
from typing import Dict, Tuple

# Simple lexicon (expand anytime)
MOOD_LEXICON: Dict[str, set[str]] = {
    "happy": {
        "happy","joy","excited","fun","party","energetic","dance","vibe","good","great","cheerful","uplift","smile"
    },
    "sad": {
        "sad","down","blue","depressed","cry","lonely","heartbroken","miss","nostalgic","slow","melancholy"
    },
    "chill": {
        "chill","calm","relax","lofi","coffee","study","focus","mellow","soft","ambient","smooth","peaceful"
    },
    "angry": {
        "angry","mad","rage","furious","metal","hard","scream","aggressive","intense"
    },
    "romantic": {
        "love","romance","date","valentine","kiss","crush","affection","couple","romantic","slow dance"
    },
    "workout": {
        "workout","gym","run","pump","cardio","training","HIIT","power","beast","motivation"
    },
    "sleep": {
        "sleep","bedtime","asleep","doze","night","lullaby","soothing","white noise"
    }
}

def _normalize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [tok for tok in text.split() if tok]

def detect_mood(user_text: str) -> Tuple[str, float, Dict[str, int]]:
    """
    Returns: (mood, confidence [0..1], raw_scores per mood)
    """
    toks = _normalize(user_text or "")
    scores: Dict[str, int] = {m: 0 for m in MOOD_LEXICON}

    for m, vocab in MOOD_LEXICON.items():
        for t in toks:
            if t in vocab:
                scores[m] += 1

    # fallback if nothing matched
    best_mood = "chill"
    best_score = 0
    for m, sc in scores.items():
        if sc > best_score:
            best_mood, best_score = m, sc

    # heuristic confidence: sigmoid-ish over hits
    conf = 0.15 if best_score == 0 else min(0.95, 0.45 + 0.1 * best_score)
    return best_mood, conf, scores
