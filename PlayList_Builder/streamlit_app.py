# streamlit_app.py
import os
import requests
import streamlit as st
from dotenv import load_dotenv, find_dotenv

from app.spotify import generate_playlist_from_user_settings
from app.llm_helper import generate_playlist_description  # optional; has safe fallback


# ----------------------------------
# Env / config
# ----------------------------------
# Load .env from project root or current dir (works no matter where you run from)
# Explicitly load .env file from the same directory as the script
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path, override=False)

API_BASE = os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000")
API_KEY  = os.getenv("AGENTS_API_KEY",  "dev-key-change-me")  # must match FastAPI

# ----------------------------------
# Page config & simple styles
# ----------------------------------
st.set_page_config(
    page_title="🎵 Music Recommendation AI",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
:root { --primary:#1DB954; --primary-hover:#1ed760; --bg:#121212; --card-bg:#1e1e1e; --text:#fff; --text-2:#b3b3b3; --br:10px;}
.stApp { background:var(--bg); color:var(--text); }
section[data-testid="stSidebar"] { background:#181818 !important; }
.stTextInput input, .stTextArea textarea, .stSelectbox select {
  background:rgba(255,255,255,0.05)!important; color:var(--text)!important; border-radius:var(--br)!important;
  padding:10px 12px!important; border:1px solid rgba(255,255,255,0.1)!important;
}
.stButton button{ background:var(--primary); color:#fff; border:none; border-radius:var(--br);
  padding:12px 20px; font-weight:600; width:100%; }
.stButton button:hover{ background:var(--primary-hover); }
.grid{ display:grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap:1.25rem; margin-top:1rem; }
.card{ background:var(--card-bg); border:1px solid rgba(255,255,255,0.1); border-radius:var(--br); padding:1rem; }
.badge{ display:inline-block; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.12); 
  color:var(--text-2); border-radius:999px; padding:.28rem .6rem; font-size:.85rem; margin-right:.35rem; }
.track iframe{ width:100%; height:152px; border-radius:var(--br); }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;color:#1DB954;margin-bottom:.25rem;'>Music Recommendation AI</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:#b3b3b3;'>Now using the NLP agent to auto-detect mood/genre from your vibe ✨</p>", unsafe_allow_html=True)

# ----------------------------------
# Session
# ----------------------------------
if "used_track_ids" not in st.session_state:
    st.session_state.used_track_ids = set()

# ----------------------------------
# Sidebar
# ----------------------------------
with st.sidebar:
    st.subheader("Playlist Settings")

    vibe_description = st.text_area(
        "Describe your vibe",
        placeholder='e.g., "rainy bus ride, calm focus, minimal vocals"'
    )

    mood = st.selectbox(
        "Mood",
        ["Auto-detect", "happy", "sad", "energetic", "chill", "focus", "romantic", "angry", "calm"],
        index=0
    )

    activity = st.selectbox(
        "Activity",
        ["workout", "study", "party", "relax", "commute", "sleep", "none"],
        index=1
    )

    genre_or_language = st.text_input(
        "Genre",
        placeholder='Try: hip hop, r&b, lofi'
    )

    use_auto_genre = st.checkbox("Prefer auto-detected genre when available", value=True)

    limit = st.slider("Tracks per Playlist", 5, 20, 10)
    exclude_explicit = st.checkbox("Exclude explicit lyrics", value=False)

    show_debug = st.checkbox("Show analyzer debug", value=False)

    build_btn = st.button("Generate Playlist", use_container_width=True)

# ----------------------------------
# Helper: call FastAPI /analyze
# ----------------------------------
def call_analyzer(text: str):
    try:
        r = requests.post(
            f"{API_BASE}/analyze",
            json={"text": text or ""},
            headers={"x-api-key": API_KEY},
            timeout=8,
        )
        if not r.ok:
            return None
        return r.json()
    except Exception:
        return None

# ----------------------------------
# Build & render
# ----------------------------------
if build_btn:
    if not (vibe_description or "").strip():
        st.warning("Please provide a vibe description to generate a playlist.")
        st.stop()

    # 1) Ask the NLP agent to analyze the vibe text
    analysis = call_analyzer(vibe_description)
    auto_mood  = (analysis or {}).get("mood")
    auto_genre = (analysis or {}).get("genre")

    # 2) Decide final mood/genre to use
    mood_final = None if mood == "Auto-detect" else mood
    if mood_final is None:
        if analysis is None:
            mood_final = "happy"  # request failed → safe default
        else:
            mood_final = auto_mood or "happy"

    genre_final = (genre_or_language or "").strip()
    if use_auto_genre and not genre_final:
        genre_final = (auto_genre or "").strip()

    if show_debug:
        st.code({"analysis": analysis, "mood_final": mood_final, "genre_final": genre_final}, language="json")

    # 3) Build playlist
    with st.spinner("Creating your playlist..."):
        activity_val = "" if activity == "none" else activity
        st.session_state.used_track_ids = set()

        playlist_tracks, st.session_state.used_track_ids = generate_playlist_from_user_settings(
            vibe_description=vibe_description,
            mood=mood_final,
            activity=activity_val,
            genre_or_language=genre_final,
            tracks_per_playlist=limit,
            used_ids=st.session_state.used_track_ids,
            seed=42,
            exclude_explicit=exclude_explicit
        )

    # 4) Badges
    auto_mood_badge  = (mood == "Auto-detect" and bool(auto_mood))
    auto_genre_badge = (use_auto_genre and bool(auto_genre) and not (genre_or_language or "").strip())

    st.markdown(
        f"""
        <div>
          <span class="badge">Mood: {mood_final}</span>
          <span class="badge">Activity: {activity_val or '—'}</span>
          <span class="badge">Genre: {genre_final or '—'}</span>
          {'<span class="badge">Auto mood</span>' if auto_mood_badge else ''}
          {'<span class="badge">Auto genre</span>' if auto_genre_badge else ''}
          {'<span class="badge">No explicit</span>' if exclude_explicit else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

    # 5) Handle empty results
    if not playlist_tracks:
        st.error("Spotify returned no results. Try a different Genre/Language or broaden the vibe.")
        st.stop()

    # 6) Optional short description (LLM; has fallback)
    try:
        brief_in = [{"name": t["track"]["name"], "artists": t["track"]["artists"]}
                    for t in playlist_tracks if t.get("track")]
        desc = generate_playlist_description(mood=mood_final, context=activity_val or "none", tracks=brief_in)
        if desc:
            st.info(desc)
    except Exception:
        pass

    # 7) Render grid
    st.markdown('<div class="grid">', unsafe_allow_html=True)
    for item in playlist_tracks:
        tr = item.get("track") or {}
        tid = tr.get("id")
        if not tid:
            continue
        artists = ", ".join(a.get("name","") for a in tr.get("artists", []))
        score = item.get("score")
        score_txt = f"{score:.2f}" if isinstance(score, (int, float)) else "—"
        reason = item.get("reason") or ""

        embed = f"https://open.spotify.com/embed/track/{tid}?utm_source=generator"
        st.markdown(f"""
        <div class="card">
          <h4 style="margin:.25rem 0 .5rem 0;">{tr.get('name','Unknown')} — {artists}</h4>
          <div class="track"><iframe src="{embed}" frameborder="0" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe></div>
          <div style="margin-top:.5rem;">
            <span class="badge">score: {score_txt}</span>
            <span class="badge">{reason}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
