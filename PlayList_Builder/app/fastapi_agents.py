from typing import Optional, List
import os

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv

from app.mood_detector import detect_mood as detect_mood_agent
from app.llm_helper import classify_genre
from app.routes.mood_routes import router as mood_router

from app.mood_detector import _MODEL, MODEL_PATH
from fastapi import APIRouter, Depends
router = APIRouter()
# ----------------------------------
# Load env (.env in project folder)
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
    version="1.0.0",
    description="Simple NLP helper service used by the Streamlit UI."
)

# Allow local Streamlit & optional custom origins from env
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

# ----------------------------------
# Utility routes
# ----------------------------------

app.include_router(mood_router)

@app.get("/")
def root():
    return {"service": "playlist-nlp-agent", "status": "ok"}

@app.get("/health")
def health():
    return {"ok": True}

# ----------------------------------
# Endpoints
# ----------------------------------

@router.get("/mood/model_status")
def mood_model_status():
    loaded = _MODEL is not None
    labels = _MODEL.get("labels") if loaded else []
    return {
        "loaded": loaded,
        "path": MODEL_PATH,
        "labels": labels,
        "type": "tfidf+logreg" if loaded else "lexicon"
    }

app.include_router(router)

@app.post("/mood", response_model=MoodResponse, dependencies=[Depends(require_api_key)])
def api_mood(inp: TextInput):
    txt = (inp.text or "").strip()
    if not txt or len(txt) > 800:
        raise HTTPException(status_code=400, detail="Text must be 1..800 characters.")
    m_raw = detect_mood_agent(txt)
    if isinstance(m_raw, (list, tuple)):
        mood  = str(m_raw[0]) if len(m_raw) > 0 else "unknown"
        m_conf = float(m_raw[1]) if len(m_raw) > 1 else 0.5
    else:
        mood, m_conf = str(m_raw), 0.5
    return MoodResponse(mood=mood, confidence=m_conf)

@app.post("/genre", response_model=GenreResponse, dependencies=[Depends(require_api_key)])
def api_genre(inp: TextInput):
    txt = (inp.text or "").strip()
    if not txt or len(txt) > 800:
        raise HTTPException(status_code=400, detail="Text must be 1..800 characters.")
    genre, conf = classify_genre(txt)
    return GenreResponse(genre=genre, confidence=float(conf))

@app.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(require_api_key)])
def api_analyze(inp: TextInput):
    txt = (inp.text or "").strip()
    if not txt or len(txt) > 800:
        raise HTTPException(status_code=400, detail="Text must be 1..800 characters.")

    # --- mood: accept tuple/list or str ---
    m_raw = detect_mood_agent(txt)
    if isinstance(m_raw, (list, tuple)):
        mood = str(m_raw[0]) if len(m_raw) > 0 else "unknown"
        m_conf = float(m_raw[1]) if len(m_raw) > 1 else 0.5
    else:
        mood, m_conf = str(m_raw), 0.5

    # --- genre: accept tuple/list or str ---
    g_raw = classify_genre(txt)
    if isinstance(g_raw, (list, tuple)):
        genre = str(g_raw[0]) if len(g_raw) > 0 else "unknown"
        g_conf = float(g_raw[1]) if len(g_raw) > 1 else 0.5
    else:
        genre, g_conf = str(g_raw), 0.5

    return AnalyzeResponse(
        mood=mood, mood_confidence=m_conf,
        genre=genre, genre_confidence=g_conf
    )
