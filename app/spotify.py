import requests
import base64
import os
import html
from dotenv import load_dotenv
from pathlib import Path

# ----------------------------
# Load environment variables
# ----------------------------
# Always point to project root .env
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

def refresh_token_if_needed(response):
    """Refresh token if expired (HTTP 401)."""
    global SPOTIFY_TOKEN, HEADERS
    if response.status_code == 401:
        SPOTIFY_TOKEN = get_spotify_token()
        HEADERS = {"Authorization": f"Bearer {SPOTIFY_TOKEN}"}
        return True
    return False

def sp_get(url, params=None):
    """GET request to Spotify API with automatic token refresh."""
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
# Spotify Search & Track Fetch
# ----------------------------
def search_artists(query, market="IN", limit=10):
    """Search for artists by name, genre, or vibe description."""
    query = html.escape(query)
    params = {"q": query, "type": "artist", "market": market, "limit": limit}
    data = sp_get("https://api.spotify.com/v1/search", params=params)
    if data and "artists" in data:
        return data["artists"]["items"]
    return []

def get_artist_top_tracks(artist_id, market="IN", limit=20):
    """Fetch top tracks of an artist via albums."""
    albums_data = sp_get(
        f"https://api.spotify.com/v1/artists/{artist_id}/albums",
        params={"market": market, "limit": 10}
    )
    if not albums_data or "items" not in albums_data:
        return []

    tracks = []
    for album in albums_data["items"]:
        album_tracks = sp_get(
            f"https://api.spotify.com/v1/albums/{album['id']}/tracks",
            params={"market": market}
        )
        if album_tracks and "items" in album_tracks:
            tracks.extend(album_tracks["items"])
        if len(tracks) >= limit:
            break
    return tracks[:limit]

def audio_features(track_ids):
    """Get audio features for a list of track IDs (max 100 at a time)."""
    if not track_ids:
        return []
    track_ids = track_ids[:100]
    params = {"ids": ",".join(track_ids)}
    data = sp_get("https://api.spotify.com/v1/audio-features", params=params)
    if data and "audio_features" in data:
        return data["audio_features"]
    return []

# ----------------------------
# Generate Playlist by Genre
# ----------------------------
VALID_GENRES = [
    "pop","rock","hiphop","rap","edm","jazz","classical","metal",
    "blues","reggae","country","soul","punk","latin","dance","rnb"
]

def generate_playlist_by_genre(
    genre: str,
    market: str = "IN",
    per_artist_limit: int = 5,
    total_limit: int = 50,
    search_keywords: str = None,
    used_ids: set = None
):
    """
    Generate a playlist of tracks by genre (with optional keywords).
    Ensures uniqueness by excluding already used track IDs.
    """
    if used_ids is None:
        used_ids = set()

    tracks = []

    # Construct search query
    query = genre
    if search_keywords:
        query += f" {search_keywords}"

    url = "https://api.spotify.com/v1/search"
    params = {"q": query, "type": "track", "market": market, "limit": min(total_limit, 50)}

    response = requests.get(url, headers=HEADERS, params=params)
    if refresh_token_if_needed(response):
        response = requests.get(url, headers=HEADERS, params=params)

    if response.status_code == 200:
        data = response.json()
        items = data.get("tracks", {}).get("items", [])
        for item in items:
            if item["id"] in used_ids:
                continue
            track_info = {
                "track": {
                    "id": item["id"],
                    "name": item["name"],
                    "artists": [{"id": a["id"], "name": a["name"]} for a in item["artists"]],
                    "external_urls": {"spotify": item["external_urls"]["spotify"]}
                },
                "features": {}
            }
            tracks.append(track_info)
            used_ids.add(item["id"])
            if len(tracks) >= total_limit:
                break

    # Fallback with recommendations
    if not tracks:
        print("No search results found. Using Spotify Recommendations as fallback.")
        seed_genres = [g.lower() for g in [genre] if g.lower() in VALID_GENRES]
        if not seed_genres:
            seed_genres = ["pop"]  # default fallback
        rec_params = {
            "seed_genres": ",".join(seed_genres[:5]),
            "limit": min(total_limit, 50),
            "market": market
        }
        rec_data = sp_get("https://api.spotify.com/v1/recommendations", params=rec_params)
        if rec_data and "tracks" in rec_data:
            for item in rec_data["tracks"]:
                if item["id"] in used_ids:
                    continue
                track_info = {
                    "track": {
                        "id": item["id"],
                        "name": item["name"],
                        "artists": [{"id": a["id"], "name": a["name"]} for a in item["artists"]],
                        "external_urls": {"spotify": item["external_urls"]["spotify"]}
                    },
                    "features": {}
                }
                tracks.append(track_info)
                used_ids.add(item["id"])
                if len(tracks) >= total_limit:
                    break

    # Limit per artist
    if per_artist_limit:
        artist_counts = {}
        filtered_tracks = []
        for t in tracks:
            artist_id = t["track"]["artists"][0]["id"]
            artist_counts[artist_id] = artist_counts.get(artist_id, 0) + 1
            if artist_counts[artist_id] <= per_artist_limit:
                filtered_tracks.append(t)
        tracks = filtered_tracks

    # Fetch audio features
    track_ids = [t["track"]["id"] for t in tracks]
    features_list = audio_features(track_ids)
    feats_map = {f["id"]: f for f in features_list if f}
    for t in tracks:
        t["features"] = feats_map.get(t["track"]["id"], {})

    return tracks, used_ids

# ----------------------------
# Multi-Playlist Generator
# ----------------------------
def generate_multiple_playlists(
    mood: str,
    genre: str,
    context: str,
    num_playlists: int = 3,
    tracks_per_playlist: int = 10
):
    """
    Generate multiple playlists ensuring unique tracks across them.
    """
    playlists = []
    used_ids = set()

    for _ in range(num_playlists):
        playlist_tracks, used_ids = generate_playlist_by_genre(
            genre=genre,
            search_keywords=f"{mood} {context}",
            total_limit=tracks_per_playlist,
            used_ids=used_ids
        )
        playlists.append({"tracks": playlist_tracks})

    return playlists
