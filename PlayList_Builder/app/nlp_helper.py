import spacy
from app.llm_helper import generate_playlist_description

# Load English NLP model
nlp = spacy.load("en_core_web_sm")

# Define possible moods and activities to detect
MOODS = ["happy", "sad", "energetic", "chill", "focus", "romantic", "angry", "calm"]
ACTIVITIES = ["workout", "study", "party", "relax", "commute", "sleep"]

def extract_entities(text):
    """
    Extract named entities from a text using spaCy.
    
    Returns:
        list of tuples: [(entity_text, entity_label), ...]
    """
    doc = nlp(text)
    return [(ent.text, ent.label_) for ent in doc.ents]

def detect_mood_and_context(text):
    """
    Detect mood and context/activity from user text.
    
    Returns:
        tuple: (mood, context) as strings
    """
    text_lower = text.lower()
    detected_mood = next((m for m in MOODS if m in text_lower), "neutral")
    detected_context = next((c for c in ACTIVITIES if c in text_lower), "none")
    return detected_mood, detected_context

def summarize_playlist(tracks, user_text=""):
    """
    Generate a summarized playlist description dynamically.
    
    Parameters:
        tracks (list): List of track dictionaries with 'name' and 'artists'
        user_text (str): Optional user text to extract mood/context
    
    Returns:
        str: Generated playlist description
    """
    mood, context = detect_mood_and_context(user_text)
    
    # Use LLM to generate the description
    description = generate_playlist_description(
        mood=mood,
        context=context,
        tracks=tracks
    )
    return description
