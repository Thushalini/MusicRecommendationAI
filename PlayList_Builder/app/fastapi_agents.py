# app/fastapi_agents.py
from __future__ import annotations
from typing import Optional, List, Dict, Any, Callable
import os, json, httpx
import secrets, time
from fastapi import FastAPI, HTTPException, Header, Depends, APIRouter, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv

from app.mood_detector import detect_mood as detect_mood_agent
from app.llm_helper import classify_genre
from app.mood_detector import MODEL_PATH, _PIPELINE as _MODEL

from app.user_pref_manager import recommend_for_you

# NEW: OAuth/session helpers
from app.auth import (
    new_state, pop_state, create_login_redirect_url,
    exchange_code_for_tokens, fetch_spotify_me,
    create_session, get_session, ensure_fresh_access_token,
    delete_session
)


# ----------------------------------
# Load env
# ----------------------------------
load_dotenv(find_dotenv(), override=False)

# ----------------------------------
# Security (API key)
# ----------------------------------
API_KEY = os.getenv("AGENTS_API_KEY", "dev-key-change-me")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:8501")

def require_api_key(x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ----------------------------------
# App
# ----------------------------------
app = FastAPI(
    title="Playlist Builder – NLP Agent API",
    version="1.2.0",
    description="NLP helpers: mood/genre + fused mood endpoint for multi-signal inputs."
)

_default_origins: List[str] = [
    "http://localhost:8501", "http://127.0.0.1:8501",
    "http://localhost", "http://127.0.0.1"
]
_env_origins = (os.getenv("AGENTS_CORS_ORIGINS") or "").strip()
allow_origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins else _default_origins
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ----------------------------------
# OAuth Login Flow (NEW)
# ----------------------------------
router_auth = APIRouter(prefix="/spotify", tags=["spotify auth"])

@router_auth.get("/login")
def spotify_login():
    state = new_state()
    url = create_login_redirect_url(state)
    return RedirectResponse(url)

@router_auth.get("/callback")
async def spotify_callback(code: Optional[str] = None, state: Optional[str] = None):
    if not code or not state or not pop_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired state / code")

    try:
        tokens = await exchange_code_for_tokens(code)
        profile = await fetch_spotify_me(tokens["access_token"])
        sid = create_session(tokens, profile)

        # set a secure HTTP-only cookie; then redirect back to UI
        resp = RedirectResponse(url=f"{FRONTEND_URL}/?sid={sid}")
        resp.set_cookie(  # optional: keep cookie for browser-only calls
            key="sid",
            value=sid,
            httponly=True,
            secure=False,   # True in production (HTTPS)
            samesite="lax",
            max_age=30*24*3600
        )
        return resp
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@router_auth.get("/session/me")
async def session_me(request: Request, sid: Optional[str] = Query(default=None)):
    sid = sid or request.cookies.get("sid") or (request.headers.get("X-Session-Id") or "").strip()
    if not sid:
        raise HTTPException(status_code=401, detail="No session")
    rec = get_session(sid)
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid session")
    access_token, rec = await ensure_fresh_access_token(sid)
    return {
        "sid": sid,
        "profile": rec.get("profile", {}),
        "token_type": "Bearer",
        "access_token": access_token,
        "expires_at": rec["tokens"]["expires_at"],
    }


@router_auth.get("/session/by_sid")
async def session_by_sid(sid: str):
    rec = get_session(sid)
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid session")
    access_token, rec = await ensure_fresh_access_token(sid)
    return {
        "sid": sid,
        "connected": True,
        "profile": rec.get("profile", {}),
        "token_type": "Bearer",
        "access_token": access_token,
        "expires_at": rec["tokens"]["expires_at"],
    }


@router_auth.post("/session/refresh")
async def session_refresh(request: Request):
    sid = request.cookies.get("sid") or (request.headers.get("X-Session-Id") or "").strip()
    if not sid:
        raise HTTPException(status_code=401, detail="No session")
    access_token, rec = await ensure_fresh_access_token(sid)
    return {"sid": sid, "access_token": access_token, "expires_at": rec["tokens"]["expires_at"]}

@router_auth.post("/logout")
def logout(request: Request):
    sid = request.cookies.get("sid") or (request.headers.get("X-Session-Id") or "").strip()
    if sid:
        delete_session(sid)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("sid")
    return resp



# ----------------------------------
# Spotify “For You” endpoint
# ----------------------------------

router_spotify = APIRouter(prefix="/spotify", tags=["spotify"])


def _check_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

@router_spotify.get("/for_you")
async def for_you_recs(
    ok: bool = Depends(_check_api_key),
    limit: int = Query(24, ge=1, le=50),
    authorization: str = Header(default=""),
):
    # Expect user access token from Authorization: Bearer <token>
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=400, detail="Missing Spotify Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        data = await recommend_for_you(token, limit=limit)
        return {"ok": True, **data}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)





# ----------------------------------
# Optional fusion helpers (color/emoji/SAM/quiz)
# Provide safe stubs first so Pylance never flags "possibly unbound".
# ----------------------------------
def _stub_dict(*args, **kwargs): return {}
def _stub_tuple(*args, **kwargs): return ("unknown", 0.5)

color_signal: Callable[..., Dict[str, float]] = _stub_dict
emoji_signal: Callable[..., Dict[str, float]] = _stub_dict
sam_to_mood: Callable[..., Dict[str, float]] = _stub_dict  # or Tuple[str,float] in your real impl
quiz_signal: Callable[..., Dict[str, float]] = _stub_dict
rg_quiz_signal: Callable[..., Dict[str, Any]] = _stub_dict
fuse_mood_helper: Callable[..., Any] = _stub_tuple
_HAS_FUSION = False

try:
    from app.mood_fusion import fuse_mood as fuse_mood_helper  # type: ignore
    from app.mood_signals import (                           # type: ignore
        color_signal, emoji_signal, sam_to_mood,
        quiz_signal, rg_quiz_signal
    )
    _HAS_FUSION = True
except Exception:
    _HAS_FUSION = False

# If you already have a router for mood endpoints, include it too (optional).
try:
    from app.routes.mood_routes import router as mood_router  # type: ignore
except Exception:
    mood_router = None

# If you have user profile routes unrelated to Spotify, keep them:
try:
    from app.routes.user_profile_routes import router as user_profile_router  # type: ignore
except Exception:
    user_profile_router = None

# ----------------------------------
# Schemas
# ----------------------------------
class TextInput(BaseModel):
    text: str

class MoodResponse(BaseModel):
    mood: str
    confidence: float

class GenreResponse(BaseModel):
    genre: str
    confidence: float

class AnalyzeResponse(BaseModel):
    mood: str
    mood_confidence: float
    genre: Optional[str] = None
    genre_confidence: Optional[float] = None

class FuseInput(BaseModel):
    text: Optional[str] = ""
    color: Optional[str] = None
    emoji: Optional[str] = None
    valence: Optional[float] = None
    arousal: Optional[float] = None
    quiz: Optional[Dict[str, Any]] = None
    rg_quiz: Optional[Dict[str, Any]] = None

class FuseResponse(BaseModel):
    mood: str
    confidence: float
    parts: Dict[str, Any]

# ----------------------------------
# Routers
# ----------------------------------
if mood_router:
    app.include_router(mood_router, dependencies=[Depends(require_api_key)])

if user_profile_router:
    app.include_router(user_profile_router, dependencies=[Depends(require_api_key)])

app.include_router(router_spotify)
app.include_router(router_auth)

# Utility routes
@app.get("/")
def root():
    return {"service": "playlist-nlp-agent", "status": "ok"}

@app.get("/health")
def health():
    return {"ok": True}

# ----------------------------------
# Model status
# ----------------------------------
router = APIRouter()

@router.get("/mood/model_status", dependencies=[Depends(require_api_key)])
def mood_model_status():
    loaded = _MODEL is not None
    labels = _MODEL.get("labels") if loaded and isinstance(_MODEL, dict) else []
    return {
        "loaded": bool(loaded),
        "path": str(MODEL_PATH),
        "labels": labels,
        "type": "tfidf+logreg" if loaded else "lexicon"
    }

app.include_router(router)

# ----------------------------------
# Baseline endpoints (UNCHANGED)
# ----------------------------------
@app.post("/mood", response_model=MoodResponse, dependencies=[Depends(require_api_key)])
def api_mood(inp: TextInput):
    txt = (inp.text or "").strip()
    if not txt or len(txt) > 800:
        raise HTTPException(status_code=400, detail="Text must be 1..800 characters.")
    m_raw = detect_mood_agent(txt)
    if isinstance(m_raw, (list, tuple)):
        mood  = str(m_raw[0]) if len(m_raw) > 0 else "unknown"
        m_conf = float(m_raw[1]) if len(m_raw) > 1 else 0.5
    elif isinstance(m_raw, dict):
        mood  = str(m_raw.get("label", "unknown"))
        m_conf = float(m_raw.get("confidence", 0.5))
    else:
        mood, m_conf = str(m_raw), 0.5
    return MoodResponse(mood=mood, confidence=m_conf)

@app.post("/genre", response_model=GenreResponse, dependencies=[Depends(require_api_key)])
def api_genre(inp: TextInput):
    txt = (inp.text or "").strip()
    if not txt or len(txt) > 800:
        raise HTTPException(status_code=400, detail="Text must be 1..800 characters.")
    g_raw = classify_genre(txt)
    if isinstance(g_raw, (list, tuple)):
        genre = str(g_raw[0]) if len(g_raw) > 0 else "unknown"
        g_conf = float(g_raw[1]) if len(g_raw) > 1 else 0.5
    elif isinstance(g_raw, dict):
        genre = str(g_raw.get("label", "unknown"))
        g_conf = float(g_raw.get("confidence", 0.5))
    else:
        genre, g_conf = str(g_raw), 0.5
    return GenreResponse(genre=genre, confidence=g_conf)

@app.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(require_api_key)])
def api_analyze(inp: TextInput):
    txt = (inp.text or "").strip()
    if not txt or len(txt) > 800:
        raise HTTPException(status_code=400, detail="Text must be 1..800 characters.")

    # mood
    m_raw = detect_mood_agent(txt)
    if isinstance(m_raw, (list, tuple)):
        mood = str(m_raw[0]) if len(m_raw) > 0 else "unknown"
        m_conf = float(m_raw[1]) if len(m_raw) > 1 else 0.5
    elif isinstance(m_raw, dict):
        mood = str(m_raw.get("label", "unknown"))
        m_conf = float(m_raw.get("confidence", 0.5))
    else:
        mood, m_conf = str(m_raw), 0.5

    # genre
    g_raw = classify_genre(txt)
    if isinstance(g_raw, (list, tuple)):
        genre = str(g_raw[0]) if len(g_raw) > 0 else "unknown"
        g_conf = float(g_raw[1]) if len(g_raw) > 1 else 0.5
    elif isinstance(g_raw, dict):
        genre = str(g_raw.get("label", "unknown"))
        g_conf = float(g_raw.get("confidence", 0.5))
    else:
        genre, g_conf = str(g_raw), 0.5

    return AnalyzeResponse(
        mood=mood, mood_confidence=m_conf,
        genre=genre, genre_confidence=g_conf
    )

# ----------------------------------
# FUSED MOOD: /mood/fuse (UNCHANGED)
# ----------------------------------
@app.post("/mood/fuse", response_model=FuseResponse, dependencies=[Depends(require_api_key)])
def api_mood_fuse(inp: FuseInput):
    if (inp.text is None or not str(inp.text).strip()) and not any(
        [inp.color, inp.emoji, inp.valence, inp.arousal, inp.quiz, inp.rg_quiz]
    ):
        raise HTTPException(status_code=400, detail="Provide at least text or one side-signal (color/emoji/SAM/quiz/RG quiz).")

    # 1) TEXT
    text_label, text_conf, text_scores = "unknown", 0.5, {}
    if inp.text:
        m_raw = detect_mood_agent(str(inp.text).strip())
        if isinstance(m_raw, (list, tuple)):
            text_label = str(m_raw[0]) if len(m_raw) > 0 else "unknown"
            text_conf  = float(m_raw[1]) if len(m_raw) > 1 else 0.5
            if len(m_raw) > 2 and isinstance(m_raw[2], dict):
                text_scores = m_raw[2]
        elif isinstance(m_raw, dict):
            text_label  = str(m_raw.get("label", "unknown"))
            text_conf   = float(m_raw.get("confidence", 0.5))
            text_scores = dict(m_raw.get("scores", {}))
        else:
            text_label, text_conf = str(m_raw), 0.5

    # 2) SIDE SIGNALS
    color_scores: Dict[str, float] = {}
    emoji_scores: Dict[str, float] = {}
    sam_scores: Dict[str, float] = {}
    quiz_scores: Dict[str, float] = {}
    rg_dist: Dict[str, float] = {}
    rg_final: Optional[Dict[str, Any]] = None

    if _HAS_FUSION:
        try:
            if inp.color:   color_scores = dict(color_signal(inp.color)) or {}
        except Exception:   color_scores = {}
        try:
            if inp.emoji:   emoji_scores = dict(emoji_signal(inp.emoji)) or {}
        except Exception:   emoji_scores = {}
        try:
            if inp.valence is not None and inp.arousal is not None:
                sam_scores = dict(sam_to_mood(float(inp.valence), float(inp.arousal))) or {}
        except Exception:   sam_scores = {}
        try:
            if inp.quiz:    quiz_scores = dict(quiz_signal(dict(inp.quiz))) or {}
        except Exception:   quiz_scores = {}
        try:
            if getattr(inp, "rg_quiz", None):
                quiz_dict = dict(inp.rg_quiz) if inp.rg_quiz is not None else {}
                out = rg_quiz_signal({"quiz": quiz_dict}) or {}
                rg_final = out.get("final")
                rg_dist  = out.get("dist", {}) or {}
        except Exception:
            rg_final, rg_dist = None, {}

    # 3) FUSE
    if _HAS_FUSION:
        try:
            fused = fuse_mood_helper(
                text_scores=text_scores or {text_label: text_conf},
                color_scores=color_scores,
                emoji_scores=emoji_scores,
                sam_scores=sam_scores,
                quiz_scores=quiz_scores,
            )
            if isinstance(fused, (list, tuple)) and len(fused) >= 2:
                final_label = str(fused[0]); final_conf = float(fused[1])
                parts = fused[2] if len(fused) > 2 and isinstance(fused[2], dict) else {}
            elif isinstance(fused, dict):
                final_label = str(fused.get("label", text_label))
                final_conf  = float(fused.get("confidence", text_conf))
                parts = dict(fused.get("parts", {}))
            else:
                final_label, final_conf = text_label, text_conf
                parts = {}
        except Exception:
            final_label, final_conf = text_label, text_conf
            parts = {}
    else:
        final_label, final_conf = text_label, text_conf
        parts = {}

    base_parts = {
        "text": text_scores, "color": color_scores, "emoji": emoji_scores,
        "sam": sam_scores, "quiz": quiz_scores, "rg_quiz": rg_dist
    }
    if not isinstance(parts, dict):
        parts = base_parts
    else:
        parts = {**base_parts, **parts}

    if rg_final and isinstance(rg_final, dict):
        rg_label = str(rg_final.get("label", "") or "").strip()
        rg_conf  = float(rg_final.get("confidence", 0.9))
        if rg_label:
            final_label = rg_label
            final_conf  = max(final_conf, rg_conf)
            parts["rg_quiz_final"] = rg_final

    return FuseResponse(mood=final_label, confidence=final_conf, parts=parts)
