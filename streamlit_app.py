import streamlit as st
from app.spotify import search_artists, audio_features, generate_playlist_by_genre
from app.ranking import mood_targets, score_tracks, reason_string

st.title("🎵 Playlist Builder AI")

mood = st.selectbox("Mood", ["happy","sad","energetic","chill","focus","romantic","angry","calm"])
genre = st.text_input("Genre", "tamil")
context = st.selectbox("Context", ["workout","study","party","relax","commute","sleep"])
limit = st.slider("Number of tracks", 5, 50, 20)
market = st.text_input("Market", "IN")

if st.button("Build Playlist"):
    # Generate playlist based on genre
    playlist_data = generate_playlist_by_genre(genre, market, per_artist_limit=5, total_limit=limit)

    if not playlist_data:
        st.warning("No tracks found for this genre.")
    else:
        # Get mood targets
        targets = mood_targets(mood, context)

        # Score and rank tracks
        scores = {}
        for item in playlist_data:
            f = item["features"]
            t_id = item["track"]["id"]
            scores[t_id] = score_tracks(targets, {t_id: f}).get(t_id, 0.0)

        ranked = sorted(playlist_data, key=lambda x: scores.get(x["track"]["id"], 0.0), reverse=True)

        # Display tracks
        for item in ranked:
            t = item["track"]
            f = item["features"]
            artist_names = ', '.join([a['name'] for a in t['artists']])
            spotify_url = t['external_urls']['spotify']
            st.markdown(f"**{t['name']}** by {artist_names}")
            st.markdown(f"Reason: {reason_string(f)}")
            st.markdown(f"[Listen]({spotify_url})\n---")
