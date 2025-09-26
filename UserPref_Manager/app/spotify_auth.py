# app/spotify_auth.py

import os, time, secrets
import psycopg, requests
from urllib.parse import urlencode
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

# Ensure .env is loaded in this module too
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8501")
DATABASE_URL = os.getenv("DATABASE_URL")

def _get_db_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in .env or environment")
    return DATABASE_URL


SCOPES = os.getenv(
    "SPOTIFY_SCOPES",
    "user-read-email user-library-read user-top-read user-read-recently-played",
)  # space-separated as required by Spotify

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

router = APIRouter(prefix="/spotify", tags=["spotify"])

def _require_env():
    missing = [k for k, v in {
        "SPOTIFY_CLIENT_ID": CLIENT_ID,
        "SPOTIFY_CLIENT_SECRET": CLIENT_SECRET,
        "SPOTIFY_REDIRECT_URI": REDIRECT_URI,
        "DATABASE_URL": DATABASE_URL,
    }.items() if not v]
    if missing:
        raise HTTPException(status_code=500, detail=f"Missing env: {', '.join(missing)}")


def save_tokens(user_id: str, access_token: str, refresh_token: str, expires_at: int, scope: str):
    db_url = _get_db_url()  # your helper that asserts DATABASE_URL exists
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        # ensure user row exists (satisfy FK)
        cur.execute("INSERT INTO users(user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
        # upsert tokens
        cur.execute("""
            INSERT INTO user_tokens(user_id, access_token, refresh_token, expires_at, scope)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (user_id) DO UPDATE SET
              access_token=EXCLUDED.access_token,
              refresh_token=EXCLUDED.refresh_token,
              expires_at=EXCLUDED.expires_at,
              scope=EXCLUDED.scope
        """, (user_id, access_token, refresh_token, int(expires_at), scope))

@router.get("/login")
def login():
    _require_env()
    state = secrets.token_urlsafe(24)  # TODO: store+verify if you add server sessions
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "show_dialog": "false",
    }
    return RedirectResponse(f"{AUTH_URL}?{urlencode(params)}")

@router.get("/callback")
def callback(code: str, state: Optional[str] = None):
    _require_env()

    # Exchange code -> tokens
    try:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
        r = requests.post(TOKEN_URL, data=data, timeout=15)
        if not r.ok:
            # Bubble up Spotify’s error to help you debug
            return JSONResponse(status_code=r.status_code, content={"token_error": r.text})
        j = r.json()
    except Exception as ex:
        return JSONResponse(status_code=500, content={"token_exchange_exception": str(ex)})

    access = j.get("access_token")
    refresh = j.get("refresh_token")
    expires_at = int(time.time()) + int(j.get("expires_in", 3600))

    if not access:
        return JSONResponse(status_code=500, content={"error": "No access_token in response", "raw": j})

    # Fetch Spotify user profile to get the canonical user id
    try:
        me = requests.get("https://api.spotify.com/v1/me",
                          headers={"Authorization": f"Bearer {access}"}, timeout=10).json()
        user_id = me["id"]
    except Exception as ex:
        return JSONResponse(status_code=500, content={"me_exception": str(ex)})

    # Handle case where Spotify didn't return refresh_token (already authorized previously)
    if not refresh:
        try:
            with psycopg.connect(_get_db_url()) as conn, conn.cursor() as cur:
                cur.execute("SELECT refresh_token FROM user_tokens WHERE user_id=%s", (user_id,))
                row = cur.fetchone()
            if not row or not row[0]:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Missing refresh_token from Spotify; reauthorize with consent screen."},
                )
            refresh = row[0]
        except Exception as ex:
            return JSONResponse(status_code=500, content={"refresh_lookup_exception": str(ex)})

    # Persist tokens
    try:
        save_tokens(user_id, access, refresh, expires_at, j.get("scope", ""))
    except Exception as ex:
        return JSONResponse(status_code=500, content={"db_save_exception": str(ex)})

    # Redirect back to UI
    return RedirectResponse(f"{FRONTEND_URL}?user_id={user_id}")
