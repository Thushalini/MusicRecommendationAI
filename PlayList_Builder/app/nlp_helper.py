import spacy
from app.llm_helper import generate_playlist_description

nlp = spacy.load("en_core_web_sm")

def extract_entities(text):
    """
    Extract named entities from a text using spaCy.
    """
    doc = nlp(text)
    return [(ent.text, ent.label_) for ent in doc.ents]

def summarize_playlist(description):
    """
    Summarize a playlist description using a short prompt.
    """
    prompt = f"Summarize this playlist in 2-3 lines:\n{description}"
    return generate_playlist_description("neutral", "summary", [{"name": prompt, "artists": [{"name": ""}]}])
