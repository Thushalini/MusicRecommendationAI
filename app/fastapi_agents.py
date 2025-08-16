from fastapi import FastAPI
from pydantic import BaseModel
from app.llm_helper import detect_mood, classify_genre

app = FastAPI()

class TextInput(BaseModel):
    text: str

@app.post("/mood")
def receive_mood(input: TextInput):
    mood = detect_mood(input.text)
    return {"mood": mood}

@app.post("/genre")
def receive_genre(input: TextInput):
    genre = classify_genre(input.text)
    return {"genre": genre}
