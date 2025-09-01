# PlayList_Builder/app/routes/mood_routes.py
from fastapi import APIRouter
from pydantic import BaseModel
from app.mood_detector import detect_mood

router = APIRouter(prefix="/mood", tags=["mood"])

class MoodIn(BaseModel):
    text: str

class MoodOut(BaseModel):
    mood: str
    confidence: float
    scores: dict

@router.post("/detect", response_model=MoodOut)
def mood_detect(payload: MoodIn):
    mood, confidence, scores = detect_mood(payload.text)
    return {"mood": mood, "confidence": confidence, "scores": scores}
