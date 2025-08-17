import os
import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


def generate_playlist_description(mood, context, tracks, language="English"):
    """
    Generate a textual playlist description for given tracks, mood, context.
    Supports multiple languages.
    """
    if not tracks:
        return "No tracks available to generate description."

    track_list = "\n".join([
        f"{t['name']} by {', '.join([a['name'] for a in t['artists']])}"
        for t in tracks
    ])

    prompt = (
        f"Create a short, engaging playlist description in {language} for a playlist "
        f"perfect for a {context} session when feeling {mood}. "
        f"Include the following tracks naturally:\n{track_list}\n"
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
        print(f"OpenAI API error: {e}")
        return f"This playlist is perfect for a {context} session when you're feeling {mood}.\nTracks:\n{track_list}"
