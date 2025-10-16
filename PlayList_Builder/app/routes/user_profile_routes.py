# app/routes/user_profile_routes.py
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.user_profile import build_user_profile, recommend_for_user

# The parent app will inject the API-key dependency when including this router
router = APIRouter(prefix="/user", tags=["user-profile"])

class RecsRequest(BaseModel):
    vibe_description: Optional[str] = None
    mood: Optional[str] = None
    genre_or_language: Optional[str] = None
    limit: int = 12
    exclude_explicit: bool = False

@router.get("/profile")
def get_profile() -> Dict[str, Any]:
    return build_user_profile()

@router.post("/recs")
def get_recommendations(req: RecsRequest) -> Dict[str, Any]:
    try:
        tracks = recommend_for_user(
            vibe_description=req.vibe_description,
            mood=req.mood,
            genre_or_language=req.genre_or_language,
            limit=req.limit,
            exclude_explicit=req.exclude_explicit,
        )
        return {"items": tracks, "count": len(tracks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
