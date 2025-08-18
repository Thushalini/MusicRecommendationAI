import streamlit as st
from app.spotify import generate_playlist_from_user_settings

# ----------------------------
# Streamlit page config
# ----------------------------
st.set_page_config(
    page_title="🎵 Playlist Builder AI",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------
# Initialize session state
# ----------------------------
if "used_track_ids" not in st.session_state:
    st.session_state.used_track_ids = set()

# ----------------------------
# Custom CSS
# ----------------------------
st.markdown("""
<style>
:root {
    --primary: #1DB954;
    --primary-hover: #1ed760;
    --bg: #121212;
    --card-bg: #1e1e1e;
    --text: #ffffff;
    --text-secondary: #b3b3b3;
    --sidebar-bg: #181818;
    --border-radius: 8px;
}

.stApp { 
    background: var(--bg); 
    color: var(--text); 
    font-family: 'Inter', sans-serif; 
}

section[data-testid="stSidebar"] { 
    background: var(--sidebar-bg) !important; 
}

.stTextInput input, .stTextArea textarea, .stSelectbox select { 
    background: rgba(255,255,255,0.05) !important; 
    color: var(--text) !important; 
    border-radius: var(--border-radius) !important; 
    padding: 10px 12px !important; 
    border: 1px solid rgba(255,255,255,0.1) !important;
}

.stButton button {
    background-color: var(--primary);
    color: white;
    border-radius: var(--border-radius);
    font-weight: 600;
    padding: 12px 24px;
    border: none;
    width: 100%;
    transition: background-color 0.2s;
}

.stButton button:hover {
    background-color: var(--primary-hover);
}

.playlist-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
}

.playlist-card {
    background: var(--card-bg);
    padding: 1.5rem;
    border-radius: var(--border-radius);
    border: 1px solid rgba(255,255,255,0.1);
    word-wrap: break-word;
}

.track-player iframe {
    border-radius: var(--border-radius);
    width: 100%;
    height: 152px;
}

.header-container {
    text-align: center;
    margin-bottom: 2rem;
}

.header-title {
    font-size: 2.2rem;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 0.5rem;
}

.header-subtitle {
    font-size: 1rem;
    color: var(--text-secondary);
    margin-bottom: 1rem;
}

@media (max-width: 768px) {
    .playlist-grid {
        grid-template-columns: 1fr;
    }
}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Header
# ----------------------------
st.markdown("""
<div class="header-container">
    <div class="header-title">Playlist Builder AI</div>
    <div class="header-subtitle">Create personalized playlists in seconds</div>
</div>
""", unsafe_allow_html=True)

# ----------------------------
# Sidebar Inputs
# ----------------------------
with st.sidebar:
    st.subheader("Playlist Settings")
    vibe_description = st.text_area("Describe your vibe", placeholder="E.g. 'Upbeat songs for a road trip'")
    
    mood = st.selectbox(
        "Mood",
        ["happy", "sad", "energetic", "chill", "focus", "romantic", "angry", "calm"],
        index=0
    )

    activity = st.selectbox(
        "Activity",
        ["workout", "study", "party", "relax", "commute", "sleep", "none"],
        index=0
    )
    
    genre_or_language = st.text_input("Genre/Language", placeholder="Type a genre or language")
    
    limit = st.slider("Tracks per Playlist", 5, 20, 10)
    
    build_btn = st.button("Generate Playlist", use_container_width=True)

# ----------------------------
# Playlist Generation & Display
# ----------------------------
if build_btn:
    if not vibe_description.strip():
        st.warning("Please provide a vibe description to generate a playlist.")
    else:
        with st.spinner("Creating your playlist..."):
            activity_val = "" if activity == "none" else activity

            # Generate playlist with correct genre/language filtering
            playlist_tracks, st.session_state.used_track_ids = generate_playlist_from_user_settings(
                vibe_description=vibe_description,
                mood=mood,
                activity=activity_val,
                genre_or_language=genre_or_language,
                tracks_per_playlist=limit,
                used_ids=st.session_state.used_track_ids
            )

            if not playlist_tracks:
                st.warning("Couldn't fully match your vibe. Showing top available tracks.")
            
            # Display playlist grid
            st.markdown('<div class="playlist-grid">', unsafe_allow_html=True)
            for t in playlist_tracks:
                track = t["track"]
                artist_names = ', '.join([a['name'] for a in track['artists']])
                track_id = track['id']  # Use track id directly
                spotify_embed = f"https://open.spotify.com/embed/track/{track_id}?utm_source=generator"

                st.markdown(f"""
                <div class="playlist-card">
                    <h4 style='margin-bottom:0.5rem;'>{track['name']} - {artist_names}</h4>
                    <div class="track-player">
                        <iframe src="{spotify_embed}" frameborder="0" allowfullscreen allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
