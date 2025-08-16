import os
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_playlist_description(mood, context, tracks):
    """
    Generate a textual playlist description for the given tracks, mood, and context.
    
    tracks: list of dicts like {"track": {...}, "features": {...}}
    """
    if not tracks:
        return "No tracks available to generate description."

    # Build a track list string
    track_list = "\n".join([
        f"{t['track']['name']} by {', '.join([a['name'] for a in t['track']['artists']])}" 
        for t in tracks
    ])

    # Construct a simple description using mood and context
    description = (
        f"This playlist is perfect for a {context} session when you're feeling {mood}.\n\n"
        f"Tracks included:\n{track_list}\n\n"
        f"Enjoy the music and stay in the {mood} mood!"
    )

    return description