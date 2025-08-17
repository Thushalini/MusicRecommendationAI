import streamlit as st
from app.spotify import generate_multiple_playlists, generate_playlist_by_genre
from app.ranking import mood_targets, score_tracks
from app.llm_helper import generate_playlist_description
import html

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
# Clean, Simple CSS
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

/* Input Fields */
.stTextInput input, .stTextArea textarea, .stSelectbox select { 
    background: rgba(255,255,255,0.05) !important; 
    color: var(--text) !important; 
    border-radius: var(--border-radius) !important; 
    padding: 10px 12px !important; 
    border: 1px solid rgba(255,255,255,0.1) !important;
}

/* Buttons */
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

/* Playlist Grid */
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
}

/* Track Player */
.track-player iframe {
    border-radius: var(--border-radius);
    width: 100%;
    height: 152px;
}

/* Header */
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

/* Responsive */
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
    
    user_text = st.text_area(
        "Describe your vibe", 
        placeholder="E.g. 'Upbeat Tamil songs for a road trip'"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        mood = st.selectbox(
            "Mood",
            ["happy", "sad", "energetic", "chill", "focus", "romantic", "angry", "calm"],
            index=0
        )
    
    with col2:
        context = st.selectbox(
            "Activity",
            ["workout", "study", "party", "relax", "commute", "sleep", "none"],
            index=0
        )
    
    genre = st.text_input("Genre/Language", "tamil")
    
    col3, col4 = st.columns(2)
    with col3:
        limit = st.slider("Tracks per Playlist", 5, 20, 10)
    with col4:
        market = st.text_input("Market", "IN")
    
    build_btn = st.button("Generate Playlists", use_container_width=True)

# ----------------------------
# Main Playlist Generation
# ----------------------------
if build_btn:
    with st.spinner("Creating your playlists..."):
        context_val = context if context != "none" else ""
        playlists_all = generate_multiple_playlists(
            mood=mood,
            genre=genre,
            context=f"{user_text} {context_val}".strip(),
            num_playlists=3,
            tracks_per_playlist=limit
        )

        # Fallback for empty playlists
        for i in range(len(playlists_all)):
            if not playlists_all[i]["tracks"]:
                fallback_playlist, _ = generate_playlist_by_genre(
                    genre=genre,
                    search_keywords=f"{mood} {context_val}".strip(),
                    total_limit=limit,
                    used_ids=set()
                )
                playlists_all[i]["tracks"] = fallback_playlist

        # Display playlists
        st.markdown('<div class="playlist-grid">', unsafe_allow_html=True)
        for idx, p in enumerate(playlists_all, start=1):
            ranked = p["tracks"]
            if not ranked:
                st.warning(f"Playlist #{idx} couldn't be generated. Try different settings.")
                continue

            with st.container():
                st.markdown(f"""
                <div class="playlist-card">
                    <div style='display:flex;align-items:center;margin-bottom:1rem;'>
                        <h3 style='margin:0;flex-grow:1;'>Playlist #{idx}</h3>
                        <span style='background:rgba(29,185,84,0.2);color:var(--primary);padding:4px 10px;border-radius:20px;font-size:0.8rem;'>
                            {len(ranked)} tracks
                        </span>
                    </div>
                """, unsafe_allow_html=True)

                description = generate_playlist_description(mood, context_val, [t["track"] for t in ranked])
                st.caption(description)

                for t in ranked:
                    track = t["track"]
                    artist_names = ', '.join([a['name'] for a in track['artists']])
                    spotify_url = track['external_urls']['spotify']
                    track_id = spotify_url.split('/')[-1].split('?')[0]
                    spotify_embed = f"https://open.spotify.com/embed/track/{track_id}?utm_source=generator"

                    with st.expander(f"{track['name']} - {artist_names}"):
                        st.markdown(f"""
                        <div class="track-player">
                            <iframe src="{spotify_embed}" frameborder="0" allowfullscreen allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
                        </div>
                        """, unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)