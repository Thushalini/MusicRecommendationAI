# app/fastapi_agents.py
from typing import Optional, List, Dict, Any
import os

from fastapi import FastAPI, HTTPException, Header, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv

from app.mood_detector import detect_mood as detect_mood_agent
from app.llm_helper import classify_genre
from app.mood_detector import MODEL_PATH, _PIPELINE as _MODEL

# OPTIONAL fusion helpers (color/emoji/SAM/quiz). Keep try/except to avoid crashes if files are missing.
try:
    from app.mood_fusion import fuse_mood as fuse_mood_helper
    from app.mood_signals import color_signal, emoji_signal, sam_to_mood, quiz_signal, rg_quiz_signal
    _HAS_FUSION = True
except Exception:
    _HAS_FUSION = False

# If you already have a router in app/routes/mood_routes.py that exposes /mood/fuse,
# you can still include it below. This file also exposes /mood/fuse directly.
try:
    from app.routes.mood_routes import router as mood_router
except Exception:
    mood_router = None

# ----------------------------------
# Load env
# ----------------------------------
load_dotenv(find_dotenv(), override=False)

# ----------------------------------
# Security (API key)
# ----------------------------------
API_KEY = os.getenv("AGENTS_API_KEY", "dev-key-change-me")

def require_api_key(x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# ----------------------------------
# App
# ----------------------------------
app = FastAPI(
    title="Playlist Builder – NLP Agent API",
    version="1.1.0",
    description="NLP helpers: mood/genre + fused mood endpoint for multi-signal inputs."
)

_default_origins: List[str] = [
    "http://localhost:8501", "http://127.0.0.1:8501",
    "http://localhost", "http://127.0.0.1"
]
_env_origins = os.getenv("AGENTS_CORS_ORIGINS", "").strip()
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
    # primary text + optional side-signals
    text: Optional[str] = ""
    color: Optional[str] = None
    emoji: Optional[str] = None
    # SAM (Self-Assessment Manikin) style inputs: valence/arousal in [-1..1] or [0..1]
    valence: Optional[float] = None
    arousal: Optional[float] = None
    # quiz: arbitrary dict like {"q1":"A", "q2":3, ...}
    quiz: Optional[Dict[str, Any]] = None
    rg_quiz: Optional[Dict[str, Any]] = None

class FuseResponse(BaseModel):
    mood: str
    confidence: float
    parts: Dict[str, Any]  # per-signal scores/contributions

# ----------------------------------
# Routers
# ----------------------------------
if mood_router:
    # protect your existing mood routes (including any /mood/fuse already defined there)
    app.include_router(mood_router, dependencies=[Depends(require_api_key)])

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

@router.get("/mood/model_status")
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
# Baseline endpoints
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
# FUSED MOOD: /mood/fuse (text + optional signals)
# ----------------------------------
@app.post("/mood/fuse", response_model=FuseResponse, dependencies=[Depends(require_api_key)])
def api_mood_fuse(inp: FuseInput):
    """
    Accepts text plus optional {color, emoji, valence, arousal, quiz, rg_quiz} and returns a fused mood.
    """
    if (inp.text is None or not str(inp.text).strip()) and not any([inp.color, inp.emoji, inp.valence, inp.arousal, inp.quiz, inp.rg_quiz]):
        raise HTTPException(status_code=400, detail="Provide at least text or one side-signal (color/emoji/SAM/quiz/RG quiz).")

    # --- 1) TEXT signal --------------------------------------------------------
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

    # --- 2) SIDE SIGNALS -------------------------------------------------------
    color_scores = {}
    emoji_scores = {}
    sam_scores   = {}
    quiz_scores  = {}   # tiny 3Q quiz → dist over MOODS
    rg_dist      = {}   # RG 10Q quiz → dist over MOODS
    rg_final     = None # {"label","x","y","confidence","method":"quiz_rg"}

    if _HAS_FUSION:
        if inp.color:
            try: color_scores = color_signal(inp.color)
            except Exception: color_scores = {}

        if inp.emoji:
            try: emoji_scores = emoji_signal(inp.emoji)
            except Exception: emoji_scores = {}

        if inp.valence is not None and inp.arousal is not None:
            try: sam_scores = sam_to_mood(float(inp.valence), float(inp.arousal))
            except Exception: sam_scores = {}

        if inp.quiz:
            try: quiz_scores = quiz_signal(dict(inp.quiz))
            except Exception: quiz_scores = {}

        # NEW: RG quiz (primary)
        if getattr(inp, "rg_quiz", None):
            try:
                out = rg_quiz_signal({"quiz": dict(inp.rg_quiz)})
                rg_final = out.get("final")
                rg_dist  = out.get("dist", {})
            except Exception:
                rg_final, rg_dist = None, {}

    # --- 3) FUSE ---------------------------------------------------------------
    if _HAS_FUSION:
        try:
            # Pass RG distribution as an extra channel (if your fuser supports kwargs, add it).
            fused = fuse_mood_helper(
                text_scores=text_scores or {text_label: text_conf},
                color_scores=color_scores,
                emoji_scores=emoji_scores,
                sam_scores=sam_scores,
                quiz_scores=quiz_scores,
                rg_quiz_scores=rg_dist,  # safe to pass empty {}
            )

            if isinstance(fused, (list, tuple)) and len(fused) >= 2:
                final_label = str(fused[0]); final_conf = float(fused[1])
                parts = fused[2] if len(fused) > 2 and isinstance(fused[2], dict) else {
                    "text": text_scores, "color": color_scores, "emoji": emoji_scores,
                    "sam": sam_scores, "quiz": quiz_scores, "rg_quiz": rg_dist
                }
            elif isinstance(fused, dict):
                final_label = str(fused.get("label", text_label))
                final_conf  = float(fused.get("confidence", text_conf))
                parts = dict(fused.get("parts", {
                    "text": text_scores, "color": color_scores, "emoji": emoji_scores,
                    "sam": sam_scores, "quiz": quiz_scores, "rg_quiz": rg_dist
                }))
            else:
                final_label, final_conf = text_label, text_conf
                parts = {"text": text_scores}
        except Exception:
            final_label, final_conf = text_label, text_conf
            parts = {"text": text_scores}
    else:
        final_label, final_conf = text_label, text_conf
        parts = {"text": text_scores}

    # --- 4) Prefer RG quiz as primary label if present -------------------------
    if rg_final and isinstance(rg_final, dict):
        rg_label = str(rg_final.get("label", "") or "").strip()
        rg_conf  = float(rg_final.get("confidence", 0.9))
        if rg_label:
            # Override to ensure RG is the main method
            final_label = rg_label
            final_conf  = max(final_conf, rg_conf)
            parts["rg_quiz_final"] = rg_final

    return FuseResponse(mood=final_label, confidence=final_conf, parts=parts)
