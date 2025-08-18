import os
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


def generate_playlist_description(mood, context, tracks, language="English"):
    """
    Generate a short, engaging playlist description for given tracks, mood, and context.
    Supports multiple languages.
    
    Parameters:
        mood (str): Mood of the playlist (e.g., 'happy', 'chill').
        context (str): Activity or setting (e.g., 'study', 'party').
        tracks (list): List of track dictionaries with 'name' and 'artists'.
        language (str): Language for the description.
        
    Returns:
        str: A human-readable playlist description.
    """
    if not tracks:
        return f"This playlist is perfect for a {context} session when feeling {mood}, but no tracks were found."

    # Build track list for prompt
    track_list = "\n".join([
        f"{t['name']} by {', '.join([a['name'] for a in t['artists']])}"
        for t in tracks
    ])

    # Build prompt for OpenAI
    prompt = (
        f"Create a short, engaging playlist description in {language} for a playlist "
        f"suitable for a {context} session when feeling {mood}. "
        f"Incorporate the following tracks naturally:\n{track_list}\n"
        "Make it catchy and shareable on social media."
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.7,
        )
        description = response.choices[0].message.content.strip()
        return description
    except Exception as e:
        print(f"OpenAI API error: {e}")
        # Fallback description
        return f"This playlist is perfect for a {context} session when feeling {mood}.\nTracks:\n{track_list}"
