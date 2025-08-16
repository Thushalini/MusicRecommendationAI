import requests
import base64
import os
from dotenv import load_dotenv
import random

# Load .env variables
load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

def get_spotify_token():
    """Fetch a Spotify access token using Client Credentials Flow."""
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {b64_auth_str}"}
    data = {"grant_type": "client_credentials"}
    r = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
    r.raise_for_status()
    return r.json()["access_token"]

SPOTIFY_TOKEN = get_spotify_token()
HEADERS = {"Authorization": f"Bearer {SPOTIFY_TOKEN}"}


def sp_get(url, params=None):
    """Helper function to GET from Spotify API with error handling."""
    r = requests.get(url, headers=HEADERS, params=params)
    try:
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e} | URL: {r.url}")
        return None


def search_artists(query, market="IN", limit=5):
    """Search for artists by name or genre."""
    params = {
        "q": query,
        "type": "artist",
        "market": market,
        "limit": limit
    }
    data = sp_get("https://api.spotify.com/v1/search", params=params)
    if data and "artists" in data:
        return data["artists"]["items"]
    return []


def get_artist_top_tracks(artist_id, market="IN", limit=5):
    """Fetch top tracks of an artist (via albums) accessible in the market."""
    albums_data = sp_get(f"https://api.spotify.com/v1/artists/{artist_id}/albums", params={"market": market, "limit": 10})
    if not albums_data or "items" not in albums_data:
        return []

    tracks = []
    for album in albums_data["items"]:
        album_tracks = sp_get(f"https://api.spotify.com/v1/albums/{album['id']}/tracks", params={"market": market})
        if album_tracks and "items" in album_tracks:
            tracks.extend(album_tracks["items"])
        if len(tracks) >= limit:
            break
    return tracks[:limit]


def audio_features(track_ids):
    """Get audio features for a list of track IDs."""
    if not track_ids:
        return []

    track_ids = track_ids[:100]
    params = {"ids": ",".join(track_ids)}
    data = sp_get("https://api.spotify.com/v1/audio-features", params=params)
    if data and "audio_features" in data:
        return data["audio_features"]
    return []


def generate_playlist_by_genre(genre, market="IN", per_artist_limit=5, total_limit=20, targets=None):
    """
    Generate a playlist based on genre and mood targets.
    Returns list of tracks and their audio features.
    """
    artists = search_artists(genre, market, limit=10)  # get more artists for variety
    if not artists:
        print(f"No artists found for genre '{genre}'.")
        return []

    tracks = []
    for artist in artists:
        artist_tracks = get_artist_top_tracks(artist["id"], market, limit=20)  # get more tracks
        if targets:
            # Filter tracks by audio features roughly matching mood
            artist_tracks = [
                t for t in artist_tracks
                if t.get("id")  # only if track ID exists
            ]
        if artist_tracks:
            tracks.extend(random.sample(artist_tracks, min(per_artist_limit, len(artist_tracks))))
        if len(tracks) >= total_limit:
            break

    tracks = tracks[:total_limit]
    track_ids = [t["id"] for t in tracks if t.get("id")]
    features = audio_features(track_ids)
    features_map = {f["id"]: f for f in features if f}

    return [{"track": t, "features": features_map.get(t["id"], {})} for t in tracks]