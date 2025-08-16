import os
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


def generate_playlist_description(mood, context, tracks):
    """
    Generate a textual playlist description for the given tracks, mood, and context.
    
    tracks: list of track dicts, each containing 'name' and 'artists'
    """
    if not tracks:
        return "No tracks available to generate description."

    # Build a track list string
    track_list = "\n".join([
        f"{t['name']} by {', '.join([a['name'] for a in t['artists']])}"
        for t in tracks
    ])

    # Prompt for GPT to generate a creative description
    prompt = (
        f"Create a short, engaging playlist description for a playlist that is perfect for a {context} session "
        f"when feeling {mood}. Include the following tracks in a natural, friendly style:\n{track_list}\n"
        f"Make it catchy and suitable for sharing on social media."
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
        # Fallback to simple description if GPT fails
        fallback_description = (
            f"This playlist is perfect for a {context} session when you're feeling {mood}.\n\n"
            f"Tracks included:\n{track_list}\n\n"
            f"Enjoy the music and stay in the {mood} mood!"
        )
        print(f"OpenAI API error: {e}")
        return fallback_description
