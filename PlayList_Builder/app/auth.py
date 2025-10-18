# app/auth.py
from __future__ import annotations
import os, json, time, base64, secrets, httpx
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=False)

# ---- ENV ----
SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/spotify/callback")
FRONTEND_URL          = os.getenv("FRONTEND_URL", "http://127.0.0.1:8501")

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise RuntimeError("Missing SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET in .env")

# ---- Storage (file-backed) ----
DATA_DIR = Path(__file__).resolve().parent.parent / ".appdata"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE   = DATA_DIR / "oauth_state.json"     # transient "state" -> created_at
SESSIONS_FILE= DATA_DIR / "sessions.json"        # sid -> {tokens + profile}

def _load(path: Path) -> Dict[str, Any]:
    if not path.exists(): return {}
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return {}

def _save(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

# ---- OAuth helpers ----
SCOPES = "user-read-email user-read-private playlist-read-private user-library-read"

def create_login_redirect_url(state: str) -> str:
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "show_dialog": "true",
    }
    return f"https://accounts.spotify.com/authorize?{urlencode(params)}"

def new_state() -> str:
    s = secrets.token_urlsafe(24)
    states = _load(STATE_FILE)
    states[s] = {"created_at": int(time.time())}
    _save(STATE_FILE, states)
    return s

def pop_state(state: str) -> bool:
    states = _load(STATE_FILE)
    if state in states:
        # expire after 10 minutes
        ok = (int(time.time()) - int(states[state]["created_at"])) <= 600
        states.pop(state, None)
        _save(STATE_FILE, states)
        return ok
    return False

async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    auth = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth}"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
            },
        )
        r.raise_for_status()
        data = r.json()
        # normalize expires_at (epoch)
        data["expires_at"] = int(time.time()) + int(data.get("expires_in", 3600))
        return data

async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    auth = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth}"},
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
        r.raise_for_status()
        data = r.json()
        # carry forward refresh_token if not returned
        if "refresh_token" not in data:
            data["refresh_token"] = refresh_token
        data["expires_at"] = int(time.time()) + int(data.get("expires_in", 3600))
        return data

async def fetch_spotify_me(access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        r.raise_for_status()
        return r.json()

# ---- Session helpers ----
def create_session(tokens: Dict[str, Any], profile: Dict[str, Any]) -> str:
    sid = secrets.token_urlsafe(24)
    db  = _load(SESSIONS_FILE)
    db[sid] = {
        "created_at": int(time.time()),
        "tokens": {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_at": int(tokens.get("expires_at", 0)),
            "scope": tokens.get("scope", ""),
            "token_type": tokens.get("token_type", "Bearer"),
        },
        "profile": {
            "id": profile.get("id"),
            "email": profile.get("email"),
            "display_name": profile.get("display_name"),
            "country": profile.get("country"),
            "images": profile.get("images") or [],
            "product": profile.get("product"),
        },
    }
    _save(SESSIONS_FILE, db)
    return sid

def get_session(sid: str) -> Optional[Dict[str, Any]]:
    return _load(SESSIONS_FILE).get(sid)

def save_session(sid: str, rec: Dict[str, Any]) -> None:
    db = _load(SESSIONS_FILE); db[sid] = rec; _save(SESSIONS_FILE, db)

def delete_session(sid: str) -> None:
    db = _load(SESSIONS_FILE)
    if sid in db:
        db.pop(sid, None)
        _save(SESSIONS_FILE, db)

def is_expired(rec: Dict[str, Any]) -> bool:
    return int(rec.get("tokens", {}).get("expires_at", 0)) - int(time.time()) <= 30

async def ensure_fresh_access_token(sid: str) -> Tuple[str, Dict[str, Any]]:
    rec = get_session(sid)
    if not rec: raise ValueError("invalid session")
    tok = rec["tokens"]
    if not is_expired(rec):
        return tok["access_token"], rec
    # refresh
    new_tok = await refresh_access_token(tok["refresh_token"])
    rec["tokens"].update({
        "access_token": new_tok["access_token"],
        "refresh_token": new_tok.get("refresh_token", tok["refresh_token"]),
        "expires_at": new_tok["expires_at"],
        "scope": new_tok.get("scope", tok.get("scope", "")),
        "token_type": new_tok.get("token_type", tok.get("token_type", "Bearer")),
    })
    save_session(sid, rec)
    return rec["tokens"]["access_token"], rec
