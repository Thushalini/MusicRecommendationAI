from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.llm_helper import detect_mood, classify_genre

app = FastAPI(title="Playlist AI Agents", description="Mood and Genre Detection API")

# ----------------------------
# Request & Response Models
# ----------------------------
class TextInput(BaseModel):
    text: str

class MoodResponse(BaseModel):
    mood: str
    confidence: float  # Optional, if your model supports it

class GenreResponse(BaseModel):
    genre: str
    confidence: float  # Optional, if your model supports it

class AnalyzeResponse(BaseModel):
    mood: str
    mood_confidence: float
    genre: str
    genre_confidence: float

# ----------------------------
# Mood Endpoint
# ----------------------------
@app.post("/mood", response_model=MoodResponse)
def receive_mood(input: TextInput):
    if not input.text.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty")

    mood, confidence = detect_mood(input.text)  # return both value & confidence
    return {"mood": mood, "confidence": confidence}

# ----------------------------
# Genre Endpoint
# ----------------------------
@app.post("/genre", response_model=GenreResponse)
def receive_genre(input: TextInput):
    if not input.text.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty")

    genre, confidence = classify_genre(input.text)
    return {"genre": genre, "confidence": confidence}

# ----------------------------
# Combined Analyze Endpoint
# ----------------------------
@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_text(input: TextInput):
    if not input.text.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty")

    mood, mood_conf = detect_mood(input.text)
    genre, genre_conf = classify_genre(input.text)

    return {
        "mood": mood,
        "mood_confidence": mood_conf,
        "genre": genre,
        "genre_confidence": genre_conf
    }
