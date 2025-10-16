# app/user_profile.py
from __future__ import annotations
import datetime as dt
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Set

from app.datastore import list_playlists  # kept for compatibility; may be unused
from app.spotify import generate_playlist_from_user_settings

# ---------- internal helpers ----------

def _safe_lower(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _extract_request_meta(p: Dict[str, Any]) -> Dict[str, Any]:
    req = p.get("request") or {}
    return {
        "mood": _safe_lower(req.get("mood")),
        "activity": _safe_lower(req.get("activity")),
        "genre_or_language": _safe_lower(req.get("genre_or_language")),
        "vibe_description": (req.get("vibe_description") or "").strip(),
        "exclude_explicit": bool(req.get("exclude_explicit", False)),
        "limit": int(req.get("limit", 12)),
    }

def _recency_weight(ts_iso: str) -> float:
    """Higher weight for recent items. 1.0 now → ~0.5 after ~30 days."""
    try:
        t = dt.datetime.fromisoformat(ts_iso)
    except Exception:
        return 1.0
    days = (dt.datetime.now() - t).days
    # half-life ≈ 30 days
    return float(0.5 ** (days / 30.0))

def _time_buckets(ts_iso: str) -> Tuple[str, str]:
    try:
        t = dt.datetime.fromisoformat(ts_iso)
        return (t.strftime("%a").lower(), f"{t.hour:02d}")
    except Exception:
        return ("unknown", "00")

# ---------- profile computation ----------

def build_user_profile(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Reads .appdata/saved_playlists.json (global now), aggregates signals.
    Optional user_id kept for future multi-user extension (backward-compatible).
    """
    # Prefer internal full-read if exposed; else fall back to empty list
    try:
        from app.datastore import _read_all as _read_all_private  # type: ignore
        full: List[Dict[str, Any]] = _read_all_private()
    except Exception:
        full = []

    # float-weighted accumulators
    mood_c: Dict[str, float] = defaultdict(float)
    genre_c: Dict[str, float] = defaultdict(float)
    artist_c: Dict[str, float] = defaultdict(float)
    weekday_c: Dict[str, float] = defaultdict(float)
    hour_c: Dict[str, float] = defaultdict(float)

    saved_track_ids: Set[str] = set()

    for p in full:
        created_at = p.get("created_at") or ""
        w: float = _recency_weight(created_at)
        wd, hh = _time_buckets(created_at)
        weekday_c[wd] += w
        hour_c[hh] += w

        meta = _extract_request_meta(p)
        if meta["mood"]:
            mood_c[meta["mood"]] += w
        if meta["genre_or_language"]:
            genre_c[meta["genre_or_language"]] += w

        for tr in (p.get("tracks") or []):
            # track entries saved by your streamlit save contain flat fields
            tid = tr.get("id") or (tr.get("track") or {}).get("id")
            if tid is not None:
                saved_track_ids.add(str(tid))
            for a in (tr.get("artists") or []):
                # could be name string, or dict with name/id — file may store names (strings)
                if isinstance(a, dict):
                    name = a.get("name") or ""
                else:
                    name = str(a or "")
                if name:
                    artist_c[_safe_lower(name)] += w

    def topn(d: Dict[str, float], n: int) -> List[Dict[str, Any]]:
        return [
            {"value": k, "score": round(float(v), 3)}
            for k, v in sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:n]
        ]

    profile = {
        "stats": {
            "total_playlists": len(full),
            "total_unique_tracks": len(saved_track_ids),
        },
        "top_moods": topn(mood_c, 5),
        "top_genres_or_languages": topn(genre_c, 5),
        "top_artists_by_name": topn(artist_c, 8),
        "time_patterns": {
            "top_weekdays": topn(weekday_c, 3),
            "top_hours": topn(hour_c, 3),
        },
        "saved_track_ids": list(saved_track_ids),
    }
    return profile

# ---------- recommendations ----------

def recommend_for_user(
    vibe_description: Optional[str] = None,
    mood: Optional[str] = None,
    genre_or_language: Optional[str] = None,
    limit: int = 12,
    exclude_explicit: bool = False,
) -> List[Dict[str, Any]]:
    """
    Produces 'for you' suggestions by biasing to user’s dominant mood/genre
    and avoiding already-saved tracks. Uses existing Spotify pipeline.
    """
    prof = build_user_profile()
    used_ids: Set[str] = {str(x) for x in prof.get("saved_track_ids", []) if x is not None}

    # choose defaults from profile if not provided
    def _first(lst: List[Dict[str, Any]]) -> Optional[str]:
        return lst[0]["value"] if lst else None

    mood = _safe_lower(mood) or _first(prof.get("top_moods", [])) or "chill"
    genre_or_language = (
        _safe_lower(genre_or_language)
        or _first(prof.get("top_genres_or_languages", []))
        or None
    )
    # mild personalization in vibe text if missing
    if not (vibe_description or "").strip():
        vibe_description = f"Songs aligned with my usual {mood} vibe"

    # ask for a bit more than needed then trim (helps novelty after filtering)
    ask = max(20, int(limit) * 2)

    tracks, _ = generate_playlist_from_user_settings(
        vibe_description=vibe_description or "",
        mood=mood,
        activity=None,
        genre_or_language=genre_or_language,
        tracks_per_playlist=ask,
        used_ids=used_ids,
        seed=None,
        exclude_explicit=exclude_explicit,
    )
    # Drop any that are already saved (defensive) and trim to limit.
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for t in tracks:
        tid = t.get("id") or (t.get("track") or {}).get("id")
        tid = str(tid) if tid is not None else None
        if not tid or tid in seen or tid in used_ids:
            continue
        seen.add(tid)
        out.append(t)
        if len(out) >= limit:
            break
    return out
