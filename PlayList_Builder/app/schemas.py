from typing import Literal, Optional, List
from pydantic import BaseModel, Field

Mood = Literal["happy","sad","energetic","chill","focus","romantic","angry","calm"]
Context = Literal["workout","study","party","relax","commute","sleep"]

class BuildPlaylistRequest(BaseModel):
    mood: Mood
    genre: str = Field(min_length=2, max_length=40)
    context: Optional[Context] = None
    market: str = "IN"
    limit: int = Field(default=20, ge=5, le=50)

class TrackOut(BaseModel):
    name: str
    artist: str
    spotify_url: str
    reason: str

class BuildPlaylistResponse(BaseModel):
    playlist_title: str
    tracks: List[TrackOut]
    explainability: str
