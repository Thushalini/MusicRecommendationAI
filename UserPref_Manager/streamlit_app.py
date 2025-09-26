# streamlit_app.py

import os
import requests
import streamlit as st

# -----------------------------
# Config
# -----------------------------
API_URL = os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="User Preference Manager", page_icon="🎵", layout="wide")
st.title("🎶 Music Recommendation System")

# -----------------------------
# Identify user from query params (FastAPI redirects with ?user_id=...)
# -----------------------------
user_id = st.query_params.get("user_id", None)

if not user_id:
    st.info("Please sign in with Spotify to continue.")
    st.link_button("🔐 Login with Spotify", f"{API_URL}/spotify/login")
    st.stop()

# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.header("You are signed in")
st.sidebar.success(f"Spotify user: `{user_id}`")

genre = st.sidebar.text_input("Preferred Genre (optional)", "")
mood  = st.sidebar.selectbox(
    "Mood (optional)",
    ["", "happy", "sad", "energetic", "chill", "focus", "romantic", "angry", "calm"],
    index=0,
)
artists_csv = st.sidebar.text_input("Artist IDs or names (comma-separated, optional)", "")
k = st.sidebar.slider("Number of Recommendations", 1, 20, 8)

st.sidebar.markdown("---")
colA, colB = st.sidebar.columns(2)
with colA:
    if st.button("🔄 Sync Library"):
        try:
            res = requests.post(f"{API_URL}/spotify/sync/{user_id}", timeout=120)
            if res.ok:
                st.sidebar.success("Library synced.")
                st.sidebar.json(res.json())
            else:
                st.sidebar.error(f"Sync error {res.status_code}")
                st.sidebar.code(res.text)
        except Exception as e:
            st.sidebar.error(f"Sync failed: {e}")

with colB:
    if st.button("🩺 API Health"):
        try:
            res = requests.get(f"{API_URL}/health", timeout=5)
            st.sidebar.success(res.json())
        except Exception as e:
            st.sidebar.error(f"API not reachable: {e}")

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Log out"):
    st.query_params.clear()
    st.rerun()

# -----------------------------
# Main: Recommendations
# -----------------------------
st.subheader("Recommendations")

def _render_recs(data: dict):
    cands = data.get("candidates", [])
    if not cands:
        st.warning("No candidates found. Try syncing your library and/or remove filters.")
        return
    for c in cands:
        st.write(f"🎵 **Track ID:** {c['track_id']} · score {c['score']:.3f}")
    with st.expander("Debug signals"):
        st.json(data.get("explanations", {}))

if st.button("Get Recommendations"):
    need = {
        "genre": (genre or None),
        "mood": (mood or None),
        "artists": [a.strip() for a in artists_csv.split(",") if a.strip()] or None,
    }
    payload = {"user_id": user_id, "k": k, "need": need}
    try:
        res = requests.post(f"{API_URL}/recommend", json=payload, timeout=30)
        if not res.ok:
            st.error(f"Error {res.status_code}: {res.text}")
        else:
            _render_recs(res.json())
    except Exception as e:
        st.error(f"Failed to connect: {e}")

# -----------------------------
# Search (name / lyrics later)
# -----------------------------
st.subheader("Search")
q = st.text_input("Song name or partial lyrics")
if st.button("Search"):
    if len(q.strip()) < 2:
        st.warning("Please enter at least 2 characters.")
    else:
        try:
            res = requests.get(f"{API_URL}/search", params={"q": q, "limit": 25}, timeout=20)
            if res.ok:
                for h in res.json().get("results", []):
                    st.write(f"🔎 {h['name']} — {h.get('artist','?')}  (id: {h['track_id']})")
            else:
                st.error(f"Search error {res.status_code}: {res.text}")
        except Exception as e:
            st.error(f"Search failed: {e}")
