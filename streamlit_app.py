import streamlit as st
from app.spotify import search_artists, generate_playlist_by_genre
from app.ranking import mood_targets, score_tracks, reason_string
from app.llm_helper import generate_playlist_description
import html

st.set_page_config(
    page_title="🎵 Playlist Builder AI",
    page_icon="🎧",
    layout="wide"
)

# ----------------------------
# Modern Grid CSS
# ----------------------------
st.markdown("""
<style>
/* App background */
.stApp {
    background: #121212;
    color: #fff;
    font-family: "Inter", sans-serif;
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background: #1c1c1c;
    padding: 1rem;
    border-radius: 12px;
}
section[data-testid="stSidebar"] h1,h2,h3,label,p {
    color: #f5f5f5 !important;
}

/* Buttons */
.stButton button {
    background-color: #1DB954;
    color: #fff;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.6rem 1rem;
    transition: 0.3s ease;
}
.stButton button:hover {
    background-color: #1ed760;
    transform: scale(1.03);
}

/* Playlist Grid */
.playlist-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 1.5rem;
    margin-top: 1rem;
}

/* Playlist card */
.playlist-card {
    background: #1f1f1f;
    padding: 1rem;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.playlist-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 24px rgba(0,0,0,0.5);
}

/* Expander styling */
.streamlit-expanderHeader {
    font-weight: 600;
    color: #1DB954 !important;
}

/* Spotify iframe */
iframe {
    border-radius: 10px;
    margin-top: 0.3rem;
}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Title
# ----------------------------
st.markdown("<h1 style='text-align:center; font-weight:700; color:white;'>🎧 Playlist Builder AI</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; font-size:16px; color:#ccc;'>Generate AI-powered playlists based on mood, genre & context 🎶</p>", unsafe_allow_html=True)

# ----------------------------
# Sidebar Inputs
# ----------------------------
with st.sidebar:
    st.header("🎛️ Playlist Settings")
    user_text = st.text_area("Optional mood/genre input:")
    mood = st.selectbox("Mood", ["happy","sad","energetic","chill","focus","romantic","angry","calm"], index=0)
    genre = st.text_input("Genre", "tamil")
    context = st.selectbox("Context", ["workout","study","party","relax","commute","sleep"], index=0)
    limit = st.slider("Number of tracks", 5, 50, 20)
    market = st.text_input("Market", "IN")
    build_btn = st.button("🚀 Build Playlists", use_container_width=True)

# ----------------------------
# Build Playlists
# ----------------------------
if build_btn:
    agent_data = {
        "mood": html.escape(mood),
        "genre": html.escape(genre),
        "context": html.escape(context),
        "market": html.escape(market),
        "limit": limit
    }

    playlists_all = []
    for _ in range(3):
        seeds = search_artists(agent_data["genre"], agent_data["market"], limit=5)
        targets = mood_targets(agent_data["mood"], agent_data["context"])
        playlist_data = generate_playlist_by_genre(agent_data["genre"], agent_data["market"], per_artist_limit=5, total_limit=limit)

        if not playlist_data:
            playlists_all.append(None)
            continue

        feats_map = {t["track"]["id"]: t["features"] for t in playlist_data}
        scores = score_tracks(targets, feats_map)
        ranked = sorted(playlist_data, key=lambda t: scores.get(t["track"]["id"],0.0), reverse=True)[:limit]
        playlists_all.append(ranked)

    # ----------------------------
    # Playlist Grid Container
    # ----------------------------
    st.markdown('<div class="playlist-grid">', unsafe_allow_html=True)
    
    for i, ranked in enumerate(playlists_all, start=1):
        if ranked:
            st.markdown('<div class="playlist-card">', unsafe_allow_html=True)
            st.subheader(f"🎶 Playlist #{i}")
            description = generate_playlist_description(agent_data["mood"], agent_data["context"], [t["track"] for t in ranked])
            st.write(description)

            for t in ranked:
                track = t["track"]
                f = t["features"]
                artist_names = ', '.join([a['name'] for a in track['artists']])
                spotify_url = track['external_urls']['spotify']
                spotify_embed = spotify_url.replace("open.spotify.com/track/", "open.spotify.com/embed/track/")
                
                with st.expander(f"{track['name']} - {artist_names}"):
                    st.write(f"**Reason:** {reason_string(f)}")
                    st.markdown(f'<iframe src="{spotify_embed}" width="100%" height="80" frameborder="0" allowtransparency="true" allow="encrypted-media"></iframe>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.warning(f"No tracks found for Playlist #{i}.")

    st.markdown('</div>', unsafe_allow_html=True)
