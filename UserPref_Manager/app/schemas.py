# app/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class Need(BaseModel):
    mood: Optional[str] = None
    genre: Optional[str] = None
    artists: Optional[List[str]] = None  # artist ids or names

class RecommendRequest(BaseModel):
    user_id: str
    need: Optional[Need] = None
    k: int = Field(default=50, ge=1, le=200)

class Candidate(BaseModel):
    track_id: str
    score: float

class RecommendResponse(BaseModel):
    user_id: str
    candidates: List[Candidate]
    explanations: Dict[str, List[str]] = {}

class TelemetryEvent(BaseModel):
    user_id: str
    track_id: str
    event: str               # 'play_end' | 'like' | 'add_to_playlist' | 'skip'
    ts: Optional[str] = None # ISO8601; server fills if missing
    ms_played: Optional[int] = None
    liked: Optional[bool] = None
    skipped: Optional[bool] = None
    source: Optional[str] = None
