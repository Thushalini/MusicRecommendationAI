from pydantic import BaseModel
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException

from app.mood_detector import detect_mood as detect_mood_agent
from app.mood_signals import color_signal, emoji_signal, sam_to_mood, quiz_signal
from app.mood_fusion import fuse_mood

router = APIRouter(prefix="/mood", tags=["mood"])

class MoodFuseIn(BaseModel):
    text: Optional[str] = None
    color: Optional[str] = None
    emoji: Optional[str] = None
    valence: Optional[float] = None  # 0..1
    arousal: Optional[float] = None  # 0..1
    quiz: Optional[Dict[str,str]] = None  # {"energy":..,"social":..,"focus":..}

@router.post("/fuse")
def mood_fuse(body: MoodFuseIn):
    # 1) text model
    text_scores = {}
    text_label = None; text_conf = 0.0
    if body.text and body.text.strip():
        label, conf, scores = detect_mood_agent(body.text.strip())
        text_label, text_conf, text_scores = label, conf, scores

    # 2) activities
    color_scores = color_signal(body.color) if body.color else {}
    emoji_scores = emoji_signal(body.emoji) if body.emoji else {}
    sam_scores   = sam_to_mood(body.valence, body.arousal) if body.valence is not None and body.arousal is not None else {}
    quiz_scores  = quiz_signal(body.quiz or {}) if body.quiz else {}

    # 3) fuse
    fused_label, fused_conf, fused_scores = fuse_mood(
        text_scores=text_scores or {},
        color_scores=color_scores,
        emoji_scores=emoji_scores,
        sam_scores=sam_scores,
        quiz_scores=quiz_scores,
    )

    return {
        "text": {"label": text_label, "confidence": text_conf, "scores": text_scores},
        "signals": {
            "color": color_scores, "emoji": emoji_scores,
            "sam": sam_scores, "quiz": quiz_scores
        },
        "final": {"label": fused_label, "confidence": fused_conf, "scores": fused_scores}
    }

# from fastapi import APIRouter
# from pydantic import BaseModel
# from app.mood_detector import detect_mood

# router = APIRouter(prefix="/mood", tags=["mood"])

# class MoodIn(BaseModel):
#     text: str

# class MoodOut(BaseModel):
#     mood: str
#     confidence: float
#     scores: dict

# @router.post("/detect", response_model=MoodOut)
# def mood_detect(payload: MoodIn):
#     mood, confidence, scores = detect_mood(payload.text)
#     return {"mood": mood, "confidence": confidence, "scores": scores}
