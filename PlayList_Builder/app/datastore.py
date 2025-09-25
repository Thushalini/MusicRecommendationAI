# app/datastore.py
# Local JSON store for playlists at <project_root>/.appdata/saved_playlists.json
# Robust to corrupted/old formats (dict/single-object) and auto-repairs to a list.

from __future__ import annotations
import json
import uuid
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional

# Paths
_APP_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _APP_DIR.parent
_DATA_DIR = _ROOT_DIR / ".appdata"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_STORE_FILE = _DATA_DIR / "saved_playlists.json"


def _ensure_file() -> None:
    if not _STORE_FILE.exists():
        _STORE_FILE.write_text("[]", encoding="utf-8")


def _normalize_items(raw: Any) -> List[Dict[str, Any]]:
    """
    Accepts various shapes and converts to a list of playlist dicts.
    Handles:
      - list[dict] (expected)
      - {"items": list[dict]}
      - dict keyed by id: { "<id>": {...}, ... }
      - single playlist dict mistakenly saved
    """
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]

    if isinstance(raw, dict):
        # {"items": [...]}
        if isinstance(raw.get("items"), list):
            return [x for x in raw["items"] if isinstance(x, dict)]

        # dict keyed by id
        values = [v for v in raw.values() if isinstance(v, dict)]
        if values:
            return values

        # single object that looks like a playlist
        if any(k in raw for k in ("id", "title", "tracks")):
            return [raw]

    return []


def _read_all() -> List[Dict[str, Any]]:
    _ensure_file()
    try:
        text = _STORE_FILE.read_text(encoding="utf-8") or "[]"
        raw = json.loads(text)
    except Exception:
        # Corrupted JSON → back up and reset
        try:
            _STORE_FILE.rename(_STORE_FILE.with_suffix(".bak"))
        except Exception:
            pass
        _STORE_FILE.write_text("[]", encoding="utf-8")
        return []

    items = _normalize_items(raw)

    # If original wasn’t a clean list, auto-repair the file to list form
    if not isinstance(raw, list):
        try:
            _write_all(items)
        except Exception:
            pass

    return items


def _write_all(items: List[Dict[str, Any]]) -> None:
    _STORE_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def save_playlist(
    title: str,
    request_meta: Dict[str, Any],
    tracks: List[Dict[str, Any]],
    description: str = "",
    playlist_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a playlist to the JSON store and return the saved object."""
    items = _read_all()
    pid = playlist_id or f"{dt.datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    payload: Dict[str, Any] = {
        "id": pid,
        "title": (title or "").strip() or f"Playlist {pid}",
        "created_at": _now_iso(),
        "request": request_meta,
        "description": description or "",
        "tracks": tracks,
    }
    items.append(payload)
    _write_all(items)
    return payload


def list_playlists() -> List[Dict[str, Any]]:
    """Return lightweight summaries (newest first)."""
    items = _read_all()
    out: List[Dict[str, Any]] = []
    for x in reversed(items):
        req = x.get("request", {}) if isinstance(x, dict) else {}
        out.append({
            "id": x.get("id") if isinstance(x, dict) else None,
            "title": x.get("title") if isinstance(x, dict) else "Untitled",
            "created_at": x.get("created_at") if isinstance(x, dict) else "",
            "n_tracks": len((x.get("tracks") or [])) if isinstance(x, dict) else 0,
            "mood": req.get("mood"),
            "activity": req.get("activity"),
            "genre_or_language": req.get("genre_or_language"),
        })
    return out


def load_playlist(playlist_id: str) -> Optional[Dict[str, Any]]:
    items = _read_all()
    for x in items:
        if isinstance(x, dict) and x.get("id") == playlist_id:
            return x
    return None


def delete_playlist(playlist_id: str) -> bool:
    items = _read_all()
    new_items = [x for x in items if not (isinstance(x, dict) and x.get("id") == playlist_id)]
    if len(new_items) == len(items):
        return False
    _write_all(new_items)
    return True
