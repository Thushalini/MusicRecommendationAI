import streamlit as st
from app.spotify import search_artists, generate_playlist_by_genre
from app.ranking import mood_targets, score_tracks, reason_string
from app.llm_helper import generate_playlist_description
import html
import random

st.set_page_config(
    page_title="🎵 Playlist Builder AI",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------
# Modern CSS with Glassmorphism Effects
# ----------------------------
st.markdown("""
<style>
/* Base styles */
:root {
    --primary: #1DB954;
    --primary-hover: #1ed760;
    --bg: #0f0f0f;
    --card-bg: rgba(30, 30, 30, 0.7);
    --text: #ffffff;
    --text-secondary: #b3b3b3;
    --sidebar-bg: rgba(20, 20, 20, 0.8);
    --border-radius: 16px;
}

/* App background with subtle gradient */
.stApp {
    background: linear-gradient(135deg, #0f0f0f 0%, #1a1a1a 100%);
    color: var(--text);
    font-family: 'Inter', 'Segoe UI', Roboto, sans-serif;
}

/* Sidebar styling with glass effect */
section[data-testid="stSidebar"] {
    background: var(--sidebar-bg) !important;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-right: 1px solid rgba(255, 255, 255, 0.1);
}

section[data-testid="stSidebar"] h1,h2,h3,label,p {
    color: var(--text) !important;
}

/* Input fields */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    background: rgba(255, 255, 255, 0.1) !important;
    color: var(--text) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 12px !important;
    padding: 10px 12px !important;
}

.stSlider .st-ae {
    color: var(--primary) !important;
}

/* Buttons with modern hover effects */
.stButton button {
    background-color: var(--primary);
    color: white;
    border-radius: 12px;
    font-weight: 600;
    padding: 0.7rem 1.2rem;
    border: none;
    transition: all 0.3s ease;
    width: 100%;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.stButton button:hover {
    background-color: var(--primary-hover);
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(29, 185, 84, 0.2);
}

/* Playlist Grid with responsive layout */
.playlist-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
}

/* Playlist card with glassmorphism effect */
.playlist-card {
    background: var(--card-bg);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    padding: 1.5rem;
    border-radius: var(--border-radius);
    border: 1px solid rgba(255, 255, 255, 0.1);
    transition: all 0.3s ease;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.playlist-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
    border-color: rgba(29, 185, 84, 0.3);
}

/* Track expander styling */
.streamlit-expanderHeader {
    font-weight: 600;
    color: var(--primary) !important;
    font-size: 1rem;
}

.streamlit-expanderContent {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 0 0 12px 12px;
    padding: 1rem;
}

/* Spotify player styling */
.track-player {
    margin: 12px 0;
    border-radius: 12px;
    overflow: hidden;
}

.track-player iframe {
    border-radius: 12px;
    margin-top: 0.5rem;
    width: 100%;
    height: 152px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

/* Custom scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
}

::-webkit-scrollbar-thumb {
    background: var(--primary);
    border-radius: 4px;
}

/* Header styling */
.header-container {
    text-align: center;
    margin-bottom: 2rem;
    position: relative;
    padding: 1.5rem 0;
}

.header-container::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 25%;
    width: 50%;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--primary), transparent);
}

/* Loading animation */
@keyframes pulse {
    0% { opacity: 0.6; }
    50% { opacity: 1; }
    100% { opacity: 0.6; }
}

.stSpinner > div {
    animation: pulse 1.5s infinite ease-in-out;
    background-color: var(--primary);
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .playlist-grid {
        grid-template-columns: 1fr;
    }
}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Header with Animated Gradient
# ----------------------------
st.markdown("""
<div class="header-container">
    <h1 style='font-size: 2.5rem; font-weight: 800; margin-bottom: 0.5rem; background: linear-gradient(90deg, #1DB954, #25FEFD); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>Playlist Builder AI</h1>
    <p style='font-size: 1.1rem; color: var(--text-secondary); margin-top: 0;'>Craft perfect playlists powered by AI 🎶</p>
</div>
""", unsafe_allow_html=True)

# ----------------------------
# Sidebar with Modern Inputs
# ----------------------------
with st.sidebar:
    st.markdown("""
    <div style='display: flex; align-items: center; margin-bottom: 1.5rem;'>
        <h2 style='margin: 0;'>🎛️ Playlist Settings</h2>
    </div>
    """, unsafe_allow_html=True)
    
    with st.container():
        user_text = st.text_area("Describe your vibe:", placeholder="E.g. 'Upbeat Tamil songs for a road trip'")
        
        col1, col2 = st.columns(2)
        with col1:
            mood = st.selectbox("Mood", ["happy", "sad", "energetic", "chill", "focus", "romantic", "angry", "calm"], index=0)
        with col2:
            context = st.selectbox("Context", ["workout", "study", "party", "relax", "commute", "sleep"], index=0)
        
        genre = st.text_input("Genre", "tamil", help="Enter music genre like pop, rock, hiphop")
        
        col3, col4 = st.columns(2)
        with col3:
            limit = st.slider("Tracks", 5, 50, 20)
        with col4:
            market = st.text_input("Market", "IN", help="Country code like US, UK, JP")
        
        build_btn = st.button("✨ Generate Playlists", use_container_width=True)

# ----------------------------
# Main Content Area
# ----------------------------
if build_btn:
    with st.spinner('🎧 Crafting diverse playlists with unique artists...'):
        agent_data = {
            "mood": html.escape(mood),
            "genre": html.escape(genre),
            "context": html.escape(context),
            "market": html.escape(market),
            "limit": limit
        }

        playlists_all = []
        for _ in range(3):
            # Get mood/energy targets
            targets = mood_targets(agent_data["mood"], agent_data["context"])

            # Generate playlist with targets
            playlist_data = generate_playlist_by_genre(
                genre=agent_data["genre"],
                market=agent_data["market"],
                per_artist_limit=5,
                total_limit=agent_data["limit"] * 5,  # larger pool for filtering
                targets=targets
            )

            if not playlist_data:
                playlists_all.append(None)
                continue

            # Score tracks based on mood/energy
            feats_map = {t["track"]["id"]: t["features"] for t in playlist_data}
            scores = score_tracks(targets, feats_map)
            
            # Sort tracks by score
            ranked = sorted(playlist_data, key=lambda t: -scores.get(t["track"]["id"], 0.0))
            
            # Select tracks ensuring artist diversity
            final_tracks = []
            used_artists = set()
            for track in ranked:
                artist_id = track["track"]["artists"][0]["id"]
                if artist_id not in used_artists:
                    used_artists.add(artist_id)
                    final_tracks.append(track)
                    if len(final_tracks) >= agent_data["limit"]:
                        break
            
            # Fill remaining if not enough unique artists
            if len(final_tracks) < agent_data["limit"]:
                remaining = agent_data["limit"] - len(final_tracks)
                for track in ranked:
                    if track not in final_tracks:
                        final_tracks.append(track)
                        remaining -= 1
                        if remaining == 0:
                            break
            
            playlists_all.append(final_tracks)

    # ----------------------------
    # Playlist Grid Display
    # ----------------------------
    st.markdown("""
    <div style='margin-top: 2rem;'>
        <h2 style='margin-bottom: 1rem;'>Your AI-Generated Playlists</h2>
        <p style='color: var(--text-secondary);'>Each playlist is uniquely crafted based on your preferences</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="playlist-grid">', unsafe_allow_html=True)
    
    for i, ranked in enumerate(playlists_all, start=1):
        if ranked:
            with st.container():
                st.markdown(f"""
                <div class="playlist-card">
                    <div style='display: flex; align-items: center; margin-bottom: 1rem;'>
                        <h3 style='margin: 0; flex-grow: 1;'>🎧 Playlist #{i}</h3>
                        <span style='background: rgba(29, 185, 84, 0.2); color: var(--primary); padding: 4px 10px; border-radius: 20px; font-size: 0.8rem;'>{len(ranked)} tracks</span>
                    </div>
                """, unsafe_allow_html=True)
                
                description = generate_playlist_description(agent_data["mood"], agent_data["context"], [t["track"] for t in ranked])
                st.write(description)
                
                for t in ranked:
                    track = t["track"]
                    f = t["features"]
                    artist_names = ', '.join([a['name'] for a in track['artists']])
                    spotify_url = track['external_urls']['spotify']
                    track_id = spotify_url.split('/')[-1].split('?')[0]
                    spotify_embed = f"https://open.spotify.com/embed/track/{track_id}?utm_source=generator"
                    
                    with st.expander(f"🎵 {track['name']} - {artist_names}"):
                        st.markdown(f"**🎯 AI Selection Reason:** {reason_string(f)}")
                        st.markdown(f"""
                        <div class="track-player">
                            <iframe src="{spotify_embed}" 
                            frameborder="0" 
                            allowfullscreen="" 
                            allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" 
                            loading="lazy"></iframe>
                        </div>
                        """, unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.warning(f"Couldn't generate Playlist #{i}. Try adjusting your parameters.")

    st.markdown('</div>', unsafe_allow_html=True)
    
    # Success message
    st.success("🎉 Playlists generated successfully! Click on tracks to listen and expand for details.")
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: var(--text-secondary); margin-top: 2rem;'>
        <p>Want to refine your playlists? Adjust the settings and generate again!</p>
    </div>
    """, unsafe_allow_html=True)
