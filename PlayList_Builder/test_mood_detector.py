# test_mood_detector.py
import os
import requests
import json

# Try to import local function (if exists)
try:
    from app.llm_helper import detect_mood
except ImportError:
    detect_mood = None

API_BASE = os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000")
API_KEY  = os.getenv("AGENTS_API_KEY", "dev-key-change-me")

SAMPLES = [
    "I am super happy and smiling all day long!",
    "Feeling down and heartbroken… so sad right now.",
    "Pumped up and ready to crush my workout!",
    "It’s a rainy day, I just want to relax and focus.",
    "Romantic dinner with soft lights and wine.",
    "So angry, everything is annoying me today!",
]

def test_api():
    print("\n--- Testing FastAPI /analyze endpoint ---")
    for text in SAMPLES:
        try:
            r = requests.post(
                f"{API_BASE}/analyze",
                headers={"x-api-key": API_KEY},
                json={"text": text},
                timeout=8,
            )
            if r.ok:
                print(f"Input: {text}\n → {json.dumps(r.json(), indent=2)}\n")
            else:
                print(f"Input: {text}\n → Error {r.status_code}: {r.text}\n")
        except Exception as e:
            print(f"Input: {text}\n → Exception: {e}\n")

def test_local():
    if detect_mood is None:
        print("\n[Skipped local test] detect_mood not found in app.llm_helper")
        return
    print("\n--- Testing detect_mood() locally ---")
    for text in SAMPLES:
        try:
            mood = detect_mood(text)
            print(f"Input: {text}\n → Mood: {mood}\n")
        except Exception as e:
            print(f"Input: {text}\n → Exception: {e}\n")

if __name__ == "__main__":
    test_local()
    test_api()
