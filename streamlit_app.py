import streamlit as st
from app.spotify import search_artists, generate_playlist_by_genre, audio_features
from app.ranking import mood_targets, score_tracks, reason_string
from app.llm_helper import generate_playlist_description

st.set_page_config(
    page_title="🎵 Playlist Builder AI",
    page_icon="🎧",
    layout="wide"
)

st.title("🎵 Playlist Builder AI")
st.markdown("Generate mood-based playlists with AI assistance 🎶")

# ----------------------------
# Mock agent output for testing
# ----------------------------
mock_agent_output = {
    "mood": "happy",
    "genre": "tamil",
    "context": "workout",
    "market": "IN",
    "limit": 20
}

# ----------------------------
# User Inputs Sidebar
# ----------------------------
with st.sidebar:
    st.header("🎛️ Playlist Settings")
    mood = st.selectbox(
        "Mood",
        ["happy","sad","energetic","chill","focus","romantic","angry","calm"],
        index=0
    )
    genre = st.text_input("Genre", "tamil")
    context = st.selectbox(
        "Context",
        ["workout","study","party","relax","commute","sleep"],
        index=0
    )
    limit = st.slider("Number of tracks", 5, 50, 20)
    market = st.text_input("Market", "IN")
    build_btn = st.button("Build Playlist")

# ----------------------------
# Build Playlist
# ----------------------------
if build_btn:
    agent_data = {
        "mood": mood or mock_agent_output["mood"],
        "genre": genre or mock_agent_output["genre"],
        "context": context or mock_agent_output["context"],
        "market": market or mock_agent_output["market"],
        "limit": limit or mock_agent_output["limit"]
    }

    # Get seed artists
    seeds = search_artists(agent_data["genre"], agent_data["market"], limit=5)
    seed_ids = [s["id"] for s in seeds]

    # Mood & context targets
    targets = mood_targets(agent_data["mood"], agent_data["context"])
    sp_targets = {k: v for k, v in targets.items() if isinstance(v, (int, float)) or "tempo" in k}

    # Generate playlist
    playlist_data = generate_playlist_by_genre(
        agent_data["genre"],
        agent_data["market"],
        per_artist_limit=5,
        total_limit=agent_data["limit"]
    )

    if not playlist_data:
        st.warning("No tracks found for this genre/mood.")
    else:
        # Score and rank tracks
        feats_map = {t["track"]["id"]: t["features"] for t in playlist_data}
        scores = score_tracks(targets, feats_map)
        ranked = sorted(
            playlist_data,
            key=lambda t: scores.get(t["track"]["id"], 0.0),
            reverse=True
        )[:agent_data["limit"]]

        # Generate playlist description
        description = generate_playlist_description(
            agent_data["mood"],
            agent_data["context"],
            ranked
        )

        st.markdown("## 🎶 Playlist Overview")
        st.info(description)

        # Display tracks in columns with expanders
        st.markdown("## 🔊 Tracks")
        for t in ranked:
            track = t["track"]
            f = t["features"]
            artist_names = ', '.join([a['name'] for a in track['artists']])
            spotify_url = track['external_urls']['spotify']

            with st.expander(f"{track['name']} by {artist_names}", expanded=False):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Reason:** {reason_string(f)}")
                with col2:
                    st.markdown(f"[Listen]({spotify_url})")

        st.success(f"✅ Playlist generated! Total tracks: {len(ranked)}")
