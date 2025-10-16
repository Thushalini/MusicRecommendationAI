from __future__ import annotations

import os
import re
import math
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List, Set
from collections import defaultdict, Counter

import pandas as pd

log = logging.getLogger("genre")
if not log.handlers:
    logging.basicConfig(level=logging.INFO)

# --------------------------------------------
# Paths (env-overridable)
# --------------------------------------------
MODEL_PATH   = Path(os.getenv("GENRE_MODEL_PATH",   "app/models/genre_classifier.joblib")).resolve()  # kept for future use
DATASET_PATH = Path(os.getenv("GENRE_DATASET_PATH", "app/data/genre_dataset.csv")).resolve()

# --------------------------------------------
# Text helpers
# --------------------------------------------
_WORD_RE = re.compile(r"[a-z0-9]+")

def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _tokens(s: str) -> List[str]:
    return [w for w in _WORD_RE.findall((s or "").lower()) if len(w) >= 2]

def _ngrams(words: List[str], n: int) -> List[str]:
    return [" ".join(words[i:i+n]) for i in range(max(0, len(words)-n+1))]

def _extract_keywords(cell: str) -> Set[str]:
    """
    Extract keywords/phrases from dataset 'text' column.
    Supports comma/semicolon separated entries and free text.
    - If the cell looks like a list: split by , ; | and trim
    - Always also break into unigram tokens
    """
    cell = _norm(str(cell))
    if not cell:
        return set()

    # split by commas/semicolons/pipes if present
    parts = re.split(r"[;,|]+", cell) if re.search(r"[;,|]", cell) else [cell]
    phrases: Set[str] = set()
    for p in parts:
        p = _norm(p)
        if not p:
            continue
        phrases.add(p)
        for t in _tokens(p):
            phrases.add(t)

    return {k for k in phrases if k}

# --------------------------------------------
# In-memory keyword index (PRIMARY LOGIC)
# --------------------------------------------
# mood -> {
#   "rows": List[{"genre": str, "kw": Set[str>}],
#   "inv":  dict[keyword -> Counter({genre: count})],
# }
_INDEX: Dict[str, Dict[str, Any]] = {}
_ALL_GENRES: List[str] = []

def _build_index(df: pd.DataFrame) -> None:
    global _INDEX, _ALL_GENRES
    _INDEX = {}
    genres = set()

    def add_row(bucket: str, genre: str, kw: Set[str]):
        b = _INDEX.setdefault(bucket, {"rows": [], "inv": defaultdict(Counter), "df": Counter(), "N": 0})
        if not kw:
            return
        b["rows"].append({"genre": genre, "kw": kw})
        b["N"] += 1
        genres.add(genre)
        # update inverted + document frequency per keyword
        for k in kw:
            b["inv"][k][genre] += 1
        # count DF once per row (unique kw already)
        b["df"].update(kw)

    for _, row in df.iterrows():
        mood  = _norm(row["mood"])
        genre = str(row["genre"]).strip()
        kw    = _extract_keywords(row["text"])
        add_row(mood, genre, kw)
        add_row("__any__", genre, kw)  # global fallback bucket

    # precompute IDF per bucket
    for bucket, b in _INDEX.items():
        N = max(1, b["N"])
        b["idf"] = {k: (math.log((N) / (1.0 + df_k)) + 1.0) for k, df_k in b["df"].items()}  # +1 smoothing

    _ALL_GENRES = sorted(genres)
    log.info("[genre] Index ready. Moods=%d, GlobalRows=%d, Genres=%d",
             len([m for m in _INDEX.keys() if m != "__any__"]),
             len(_INDEX.get("__any__", {}).get("rows", [])),
             len(_ALL_GENRES))

# Load dataset & build index at import
_DF: Optional[pd.DataFrame] = None
if DATASET_PATH.exists():
    try:
        _DF = pd.read_csv(DATASET_PATH)
        for col in ("text", "mood", "genre"):
            if col not in _DF.columns:
                raise ValueError(f"Missing required column '{col}' in {DATASET_PATH}")
        # normalize required columns to strings
        _DF["text"] = _DF["text"].astype(str)
        _DF["mood"] = _DF["mood"].astype(str)
        _DF["genre"] = _DF["genre"].astype(str)
        _build_index(_DF)
    except Exception as e:
        log.error("[genre] Failed to load dataset/index: %s", e)
else:
    log.error("[genre] Dataset not found at %s. Keyword matching disabled.", DATASET_PATH)

# --------------------------------------------
# Scoring (STRICT keyword-first)
# --------------------------------------------
def _score_bucket(user_text: str, bucket_key: str) -> Tuple[str, float, Dict[str, float]]:
    """
    Score genres inside a mood bucket with STRICT keyword matching.
    - Extract user tokens + n-grams (2,3) to capture phrases
    - For each matched keyword k:
        weight = 1.0 (exact token) or 1.5 (if user n-gram equals dataset phrase)
        score += idf[k] * weight distributed to genres that contain k (via inverted index)
    - Final score per genre = sum over matched keywords
    - Require MIN_MATCHES to avoid defaulting to frequent genres (no more "always pop")
    """
    if bucket_key not in _INDEX:
        return "unknown", 0.0, {}

    b   = _INDEX[bucket_key]
    idf = b["idf"]
    inv = b["inv"]

    # build user features
    words = _tokens(user_text)
    if not words:
        return "unknown", 0.0, {}

    # candidate keyword set to check: single tokens + 2-gram/3-gram phrases
    uni  = set(words)
    bi   = set(_ngrams(words, 2))
    tri  = set(_ngrams(words, 3))
    user_keys = uni | bi | tri

    per_genre = Counter()
    matched_keywords = set()

    for k in user_keys:
        if k not in inv:
            continue
        matched_keywords.add(k)
        base = idf.get(k, 1.0)
        weight = 1.5 if (" " in k) else 1.0  # phrase bonus
        for g, cnt in inv[k].items():
            per_genre[g] += base * weight * cnt

    # enforce strictness (avoid "pop" bias)
    MIN_MATCHES = 2 if (" " not in user_text.strip()) else 1  # if user wrote a phrase, allow 1; else need ≥2 hits
    if len(matched_keywords) < MIN_MATCHES or not per_genre:
        return "unknown", 0.0, {}

    # normalize to pseudo-probabilities
    total = sum(per_genre.values())
    scores = {g: float(s) / float(total) for g, s in per_genre.items()}
    # fill zeros for stability
    for g in _ALL_GENRES:
        scores.setdefault(g, 0.0)

    # pick best with a small margin requirement
    best_g, best_s = max(scores.items(), key=lambda x: x[1])
    # if tie within small epsilon, break by number of distinct matched keywords that contributed to that genre
    EPS = 1e-9
    ties = [g for g, v in scores.items() if abs(v - best_s) <= EPS]
    if len(ties) > 1:
        # count contributing keywords per tied genre
        contrib = {g: 0 for g in ties}
        for k in matched_keywords:
            if k in inv:
                for g in ties:
                    if g in inv[k]:
                        contrib[g] += 1
        best_g = max(contrib.items(), key=lambda x: (x[1], x[0]))[0]  # more contributing kws, then alpha

    return best_g, float(scores[best_g]), dict(sorted(scores.items()))

# --------------------------------------------
# Public API
# --------------------------------------------
def classify_genre(text: str, detected_mood: str) -> Tuple[str, float, Dict[str, float]]:
    """
    STRICT keyword-based classification:
      1) Try mood bucket exact match (lowercased).
      2) If no confident keyword hit there, try global '__any__' bucket.
      3) If still nothing, return ("unknown", 0.0, {}).

    This prevents bias toward frequent genres like 'pop' by
    requiring real keyword overlap and never defaulting to a majority class.
    """
    mood_key = _norm(detected_mood)
    # 1) mood-specific
    g, c, s = _score_bucket(text, mood_key)
    if g != "unknown":
        return g, c, s

    # 2) global fallback (still strict)
    g, c, s = _score_bucket(text, "__any__")
    if g != "unknown":
        return g, c, s

    # 3) nothing matched
    return "unknown", 0.0, {}
