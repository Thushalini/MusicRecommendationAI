import requests
import base64
import os
from dotenv import load_dotenv
from pathlib import Path
import random

# ----------------------------
# Load environment variables
# ----------------------------
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID") or os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET") or os.getenv("SPOTIFY_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("Spotify API credentials not set. Please check your .env file.")

# ----------------------------
# Token Handling
# ----------------------------
def get_spotify_token():
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {b64_auth_str}"}
    data = {"grant_type": "client_credentials"}
    r = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

SPOTIFY_TOKEN = get_spotify_token()
HEADERS = {"Authorization": f"Bearer {SPOTIFY_TOKEN}"}

def refresh_token_if_needed(response):
    global SPOTIFY_TOKEN, HEADERS
    if response.status_code == 401:
        SPOTIFY_TOKEN = get_spotify_token()
        HEADERS = {"Authorization": f"Bearer {SPOTIFY_TOKEN}"}
        return True
    return False

def sp_get(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params)
        if refresh_token_if_needed(r):
            r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e} | URL: {r.url}")
        return None

# ----------------------------
# Build Search Query
# ----------------------------
def build_full_search_query(vibe_description, mood=None, activity=None, genre_or_language=None, seed=None):
    parts = [vibe_description]
    if mood:
        parts.append(mood)
    if activity:
        parts.append(activity)
    if genre_or_language:
        parts.append(genre_or_language)
    if seed is not None:
        parts.append(f"playlist_seed_{seed}")
    return " ".join(parts).strip()

# ----------------------------
# Fetch artist genres
# ----------------------------
def get_artist_genres(artist_id):
    url = f"https://api.spotify.com/v1/artists/{artist_id}"
    data = sp_get(url)
    if data and "genres" in data:
        return data["genres"]
    return []

# ----------------------------
# Fetch Tracks from Spotify & Filter by Genre/Language
# ----------------------------
def generate_playlist_by_query(search_query, genre_or_language=None, total_limit=50, used_ids=None):
    if used_ids is None:
        used_ids = set()

    tracks = []
    params = {"q": search_query, "type": "track", "limit": min(total_limit, 50)}
    data = sp_get("https://api.spotify.com/v1/search", params=params)

    if data and "tracks" in data:
        items = data.get("tracks", {}).get("items", [])
        for item in items:
            if item["id"] in used_ids:
                continue

            # Check if any artist matches the requested genre/language
            artist_matches = False
            for artist in item["artists"]:
                genres = get_artist_genres(artist["id"])
                if genre_or_language and any(genre_or_language.lower() in g.lower() for g in genres):
                    artist_matches = True
                    break

            if genre_or_language and not artist_matches:
                continue  # Skip track if artist doesn't match genre/language

            track_info = {
                "track": {
                    "id": item["id"],
                    "name": item["name"],
                    "artists": [{"id": a["id"], "name": a["name"]} for a in item["artists"]],
                    "external_urls": {"spotify": item["external_urls"]["spotify"]}
                }
            }
            tracks.append(track_info)
            used_ids.add(item["id"])
            if len(tracks) >= total_limit:
                break

    return tracks, used_ids

# ----------------------------
# Generate Playlist from User Input
# ----------------------------
def generate_playlist_from_user_settings(
    vibe_description,
    mood=None,
    activity=None,
    genre_or_language=None,
    tracks_per_playlist=15,
    used_ids=None,
    seed=None
):
    if used_ids is None:
        used_ids = set()

    # Tiered query strategy
    query_tiers = [
        {"vibe": vibe_description, "mood": mood, "activity": activity, "genre_or_language": genre_or_language},
        {"vibe": vibe_description, "mood": mood, "activity": None, "genre_or_language": genre_or_language},
        {"vibe": vibe_description, "mood": None, "activity": None, "genre_or_language": genre_or_language},
        {"vibe": vibe_description, "mood": None, "activity": None, "genre_or_language": None},
    ]

    final_tracks = []
    for tier in query_tiers:
        if len(final_tracks) >= tracks_per_playlist:
            break

        search_query = build_full_search_query(
            vibe_description=tier["vibe"],
            mood=tier["mood"],
            activity=tier["activity"],
            genre_or_language=tier["genre_or_language"],
            seed=seed
        )

        fetched_tracks, used_ids = generate_playlist_by_query(
            search_query=search_query,
            total_limit=(tracks_per_playlist - len(final_tracks)) * 3,
            used_ids=used_ids
        )

        for t in fetched_tracks:
            if t not in final_tracks:
                final_tracks.append(t)
            if len(final_tracks) >= tracks_per_playlist:
                break

    if not final_tracks:
        print("No tracks found for your settings.")
        return [], used_ids

    random.shuffle(final_tracks)
    return final_tracks[:tracks_per_playlist], used_ids

# ----------------------------
# Example usage
# ----------------------------
if __name__ == "__main__":
    tracks, _ = generate_playlist_from_user_settings(
        vibe_description="Upbeat Sinhala songs for a road trip",
        mood="happy",
        activity="road trip",
        genre_or_language="sinhala",
        tracks_per_playlist=10
    )

    for i, t in enumerate(tracks, 1):
        print(i, t["track"]["name"], "-", ", ".join([a["name"] for a in t["track"]["artists"]]))
