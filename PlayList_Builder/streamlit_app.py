# streamlit_app.py
# Modern UI + Persistent generated playlist + Save/Load to .appdata/saved_playlists.json
# (no score filtering; save uses session_state so UI doesn't vanish on click)

import os
import json
import requests
import streamlit as st
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional
import joblib # Import joblib for model loading

from app.spotify import generate_playlist_from_user_settings
from app.llm_helper import generate_playlist_description  # optional; wrapped in try/except
from app.datastore import save_playlist, list_playlists, load_playlist, delete_playlist

# -----------------------------
# Env / config
# -----------------------------
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path, override=False)

API_BASE = os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000")
API_KEY  = os.getenv("AGENTS_API_KEY",  "dev-key-change-me")

# --- MOOD-TO-GENRE MAPPING ---
# This map helps classify genres based on the detected mood, fulfilling the requirement
# to classify genres according to the detected mood using Agentic AI's output.
MOOD_TO_GENRE_MAP = {
    "happy": "pop",
    "sad": "blues",
    "energetic": "hip hop",
    "chill": "lofi",
    "focus": "classical",
    "romantic": "acoustic",
    "angry": "rock",
    "calm": "ambient",
}

# --- Load Local Genre Model ---
GENRE_MODEL_PATH = "models/genre_classifier.joblib"
loaded_genre_model = None
loaded_genre_labels = None

try:
    # Check if the model file exists before attempting to load
    if os.path.exists(GENRE_MODEL_PATH):
        with open(GENRE_MODEL_PATH, 'rb') as f:
            model_data = joblib.load(f)
            loaded_genre_model = model_data["pipeline"]
            loaded_genre_labels = model_data["labels"]
            print(f"Successfully loaded local genre model from {GENRE_MODEL_PATH}")
    else:
        print(f"Genre model not found at {GENRE_MODEL_PATH}. Will rely on API for genre.")
except Exception as e:
    print(f"Error loading genre model from {GENRE_MODEL_PATH}: {e}. Will rely on API for genre.")

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="Music Recommendation AI",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Styles
# -----------------------------
st.markdown(
    """
<style>
:root {
  --primary:#1DB954; --bg:#0f1115; --panel:#141821; --card:#141821cc;
  --muted:#9aa4b2; --text:#ecf1f8; --border:1px solid rgba(255,255,255,.08); --radius:16px;
}
.stApp { background: radial-gradient(1000px 600px at 10% -10%, #1db95422 0%, transparent 60%),
                        radial-gradient(800px 400px at 110% 10%, #4776e633 0%, transparent 55%),
                        var(--bg) !important; color:var(--text); }
section[data-testid="stSidebar"] { background: linear-gradient(180deg,#12151c,#0f1115)!important; border-right:var(--border); }
section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label { color:var(--muted)!important; }

.hero{ border:var(--border); background:linear-gradient(180deg,#141821dd,#0f1115cc); backdrop-filter:blur(8px);
       border-radius:var(--radius); padding:20px 24px; }
.hero h1{ margin:0 0 6px 0; font-size:clamp(1.4rem,2.2vw,2.1rem); letter-spacing:.3px; }
.hero p{ margin:0; color:var(--muted); }

.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"]>div, .stNumberInput input,
.stMultiSelect div[data-baseweb="select"]>div {
  background: rgba(255,255,255,.04)!important; color:var(--text)!important; border:var(--border)!important; border-radius:12px!important;
}
.stButton button{
  background:var(--primary)!important; color:#0b0d0f!important; font-weight:700!important; border-radius:12px!important;
  padding:10px 16px!important; border:none!important; transition:transform .08s ease, box-shadow .08s ease;
}
.stButton button:hover{ transform:translateY(-1px); box-shadow:0 8px 24px #1db95433; }
.stButton button:active{ transform:translateY(0) scale(.99); }

.badges{ display:flex; flex-wrap:wrap; gap:.4rem; margin:.3rem 0 .2rem; }
.badge{ display:inline-flex; align-items:center; gap:.35rem; border:var(--border); color:var(--muted);
        padding:.30rem .55rem; border-radius:999px; font-size:.85rem; background:linear-gradient(180deg,#151924,#0f1115); }

.grid{ display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:1.1rem; margin-top:.6rem; }
.card{ border:var(--border); background:var(--card); border-radius:16px; overflow:hidden; transition:transform .08s, box-shadow .08s; }
.card:hover{ transform:translateY(-2px); box-shadow:0 10px 30px rgba(0,0,0,.35); }
.card__body{ padding:12px 14px 14px; }
.card__title{ margin:.2rem 0 .55rem; font-size:15px; font-weight:700; letter-spacing:.2px; }
.track iframe{ width:100%; height:152px; border:0; }
.meta{ display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.55rem; }
.footer{ color:var(--muted); font-size:13px; text-align:center; padding:16px 0 6px; opacity:.9; }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Session state
# -----------------------------
if "used_track_ids" not in st.session_state:
    st.session_state.used_track_ids = set()
if "gen_data" not in st.session_state:
    st.session_state.gen_data = None
if "selected_saved_id" not in st.session_state:
    st.session_state.selected_saved_id = None

# -----------------------------
# Helpers
# -----------------------------
def call_analyzer(text: str) -> Optional[dict]:
    if not (text or "").strip():
        return None
    
    local_genre = None
    # Try to use the local genre model if available
    if loaded_genre_model and loaded_genre_labels:
        try:
            # Predict genre using the local model
            predicted_genre = loaded_genre_model.predict([text])[0]
            local_genre = predicted_genre
        except Exception as e:
            print(f"Error predicting genre with local model: {e}")
            # Fallback to API if local prediction fails
            pass

    # API call for mood (and potentially genre if local model fails or is not used)
    try:
        r = requests.post(
            f"{API_BASE}/analyze",
            json={"text": text},
            headers={"x-api-key": API_KEY},
            timeout=10,
        )
        api_result = r.json() if r.ok else None
        auto_mood = api_result.get("mood") if api_result else None
        auto_genre_from_api = api_result.get("genre") if api_result else None
    except Exception:
        api_result = None
        auto_mood = None
        auto_genre_from_api = None

    # Combine results: prioritize local genre if available, otherwise use API genre
    final_genre = local_genre if local_genre else auto_genre_from_api

    return {"mood": auto_mood, "genre": final_genre, "local_genre": local_genre} # Return local_genre too for debug

def render_tracks(items: List[Dict[str, Any]]):
    st.markdown('<div class="grid">', unsafe_allow_html=True)
    for item in items:
        tr = item.get("track") or {}
        tid = tr.get("id")
        if not tid:
            continue
        artists = ", ".join(a.get("name", "") for a in tr.get("artists", []))
        score = item.get("score")
        score_txt = "—" if score is None else f"{score:.2f}"
        reason = item.get("reason") or ""
        title = f"{tr.get('name','Unknown')} — {artists}"
        embed = f"https://open.spotify.com/embed/track/{tid}?utm_source=generator"
        st.markdown(
            f"""
<div class="card">
  <div class="track"><iframe src="{embed}" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe></div>
  <div class="card__body">
    <div class="card__title">{title}</div>
    <div class="meta">
      <span class="badge">score: {score_txt}</span>
      {"<span class='badge'>"+reason+"</span>" if reason else ""}
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# Header / Quick start
# -----------------------------
c1, c2 = st.columns([1, 2.2])
with c1:
    st.markdown(
        """
<div class="hero">
  <h1>Music Recommendation AI</h1>
  <p>Describe your vibe and let the AI curate a playlist tailored to your <b>mood</b>, 
  <b>genre</b>, and <b>context</b>. Powered by Spotify & smart agents.</p>
</div>
""",
        unsafe_allow_html=True,
    )
with c2:
    with st.container():
        st.markdown("### Quick Start Presets")
        q1, q2, q3 = st.columns(3)
        if q1.button("Rainy study • lofi", use_container_width=True):
            st.session_state["vibe_prefill"] = "rainy bus ride, calm focus, minimal vocals, lofi"
        if q2.button("Energetic gym • hip-hop", use_container_width=True):
            st.session_state["vibe_prefill"] = "energetic, hype, gym workout, hip hop"
        if q3.button("Sleep • piano", use_container_width=True):
            st.session_state["vibe_prefill"] = "sleep, peaceful, piano, low tempo, instrumental"

        q4, q5, q6 = st.columns(3)
        if q4.button("Party • EDM", use_container_width=True):
            st.session_state["vibe_prefill"] = "late night party, energetic, edm, high bpm"
        if q5.button("Morning jog • pop", use_container_width=True):
            st.session_state["vibe_prefill"] = "morning jog, uplifting pop, fresh vibes"
        if q6.button("Romantic evening • acoustic", use_container_width=True):
            st.session_state["vibe_prefill"] = "romantic dinner, calm acoustic, soft guitar"

        q7, q8, q9 = st.columns(3)
        if q7.button("Road trip • rock", use_container_width=True):
            st.session_state["vibe_prefill"] = "road trip, classic rock, upbeat driving songs"
        if q8.button("Meditation • ambient", use_container_width=True):
            st.session_state["vibe_prefill"] = "meditation, deep ambient, calm breathing, soundscapes"
        if q9.button("Work focus • instrumental", use_container_width=True):
            st.session_state["vibe_prefill"] = "focus work, instrumental, deep concentration, electronic minimal"

# -----------------------------
# Sidebar (controls)
# -----------------------------
with st.sidebar:
    st.subheader("Playlist Settings")

    vibe_description = st.text_area(
        "Describe your vibe",
        value=st.session_state.get("vibe_prefill", ""),
        placeholder='e.g., "rainy bus ride, calm focus, minimal vocals"',
        height=110,
    )

    mood = st.selectbox(
        "Mood",
        ["Auto-detect", "happy", "sad", "energetic", "chill", "focus", "romantic", "angry", "calm"],
        index=0,
    )

    activity = st.selectbox(
        "Activity",
        ["workout", "study", "party", "relax", "commute", "sleep", "none"],
        index=1,
    )

    prefer_auto = st.toggle("Prefer auto-detected genre if available", value=True)
    exclude_explicit = st.toggle("Exclude explicit lyrics", value=False)
    limit = st.slider("Tracks per playlist", 5, 20, 12)

    with st.expander("Advanced"):
        show_debug = st.checkbox("Show analyzer debug", value=False)

    go = st.button("Generate Playlist", use_container_width=True, key="btn_generate")

# -----------------------------
# Tabs
# -----------------------------
tab_build, tab_saved, tab_about = st.tabs(["Builder", "Saved", "How it works"])

# =============================
# Builder
# =============================
with tab_build:
    if go:
        if not (vibe_description or "").strip():
            st.warning("Please enter a short vibe description.")
            st.stop()

        # --- modern, minimal progress UI (emoji-free) ---
        class _DummyStatus:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def write(self, *a, **k): pass
            def update(self, *a, **k): pass

        def mk_status(label: str):
            try:
                return st.status(label, expanded=True)
            except Exception:
                from contextlib import contextmanager
                @contextmanager
                def _spin():
                    with st.spinner(label): yield _DummyStatus()
                return _spin()

        with mk_status("Crafting your playlist") as s:
            # Step 1: analyze
            s.write("Step 1 • Analyzing your preferences (mood/genre hints)")
            analysis = call_analyzer(vibe_description)
            auto_mood = (analysis or {}).get("mood")
            auto_genre_from_api = (analysis or {}).get("genre") # Renamed for clarity
            local_genre_from_call = (analysis or {}).get("local_genre") # Get local genre from call_analyzer

            mood_final = None if mood == "Auto-detect" else mood
            if mood_final is None:
                mood_final = auto_mood or "happy"

            # --- REVISED GENRE LOGIC ---
            # Determine genre_final based on auto_mood, local model, API, or defaults.
            genre_final = "" 
            derived_genre = None 

            # Try to derive genre from mood using the map
            if auto_mood and auto_mood in MOOD_TO_GENRE_MAP:
                derived_genre = MOOD_TO_GENRE_MAP[auto_mood]
            
            # Determine the final genre
            if derived_genre:
                genre_final = derived_genre
            elif local_genre_from_call: # Prioritize local model prediction if available
                genre_final = local_genre_from_call
            elif auto_genre_from_api: # Fallback to API's genre if mood mapping fails or local model fails
                genre_final = auto_genre_from_api
            else:
                genre_final = "pop" # Default genre if all else fails
            # --- END REVISED GENRE LOGIC ---

            if show_debug:
                debug_info = {
                    "analysis": analysis,
                    "mood_final": mood_final,
                    "genre_final": genre_final,
                    "derived_genre_from_mood": derived_genre, 
                    "auto_mood": auto_mood,
                    "auto_genre_from_api": auto_genre_from_api,
                    "local_genre_prediction": local_genre_from_call
                }
                st.code(json.dumps(debug_info, indent=2), language="json")

            # Step 2: fetch & score tracks
            s.update(label="Crafting your playlist • Retrieving candidates and scoring")
            s.write("Step 2 • Pulling tracks from Spotify and ranking for relevance")
            try:
                st.session_state.used_track_ids = set()
                playlist_items, st.session_state.used_track_ids = generate_playlist_from_user_settings(
                    vibe_description=vibe_description,
                    mood=mood_final,
                    activity=("" if activity == "none" else activity),
                    genre_or_language=genre_final, # Use the determined genre_final
                    tracks_per_playlist=limit,
                    used_ids=st.session_state.used_track_ids,
                    seed=42,
                    exclude_explicit=exclude_explicit,
                )
            except Exception as e:
                st.error(f"Failed to generate playlist: {e}")
                st.stop()

            if not playlist_items:
                st.info("No tracks found. Try broadening genre/language or disabling the explicit filter.")
                st.stop()

            # Step 3: description
            s.update(label="Crafting your playlist • Generating summary")
            s.write("Step 3 • Composing a short description of the vibe and flow")
            desc = ""
            try:
                brief = [
                    {"name": (x.get("track") or {}).get("name"),
                     "artists": (x.get("track") or {}).get("artists")}
                    for x in playlist_items if x.get("track")
                ]
                desc = generate_playlist_description(
                    mood=mood_final,
                    context=(activity if activity != "none" else "none"),
                    tracks=brief
                ) or ""
            except Exception:
                pass

            # Persist for render
            st.session_state.gen_data = {
                "items": playlist_items,
                "desc": desc,
                "mood_final": mood_final,
                "activity_final": (activity if activity != "none" else None),
                "genre_final": genre_final, # Store the final genre used
                "vibe_description": vibe_description,
                "exclude_explicit": exclude_explicit,
                "limit": limit,
            }

            # Finalize visual
            try:
                s.update(label="Playlist ready", state="complete", expanded=False)
            except Exception:
                pass

        st.toast("Playlist generated.")

    # ---- single empty-state hint & render block (no duplicates) ----
    gd = st.session_state.get("gen_data")
    empty_hint = st.empty()

    if gd:
        empty_hint.empty()

        # badges
        st.markdown(
            f"""
<div class="badges">
  <span class="badge">Mood: <strong>{gd['mood_final'] or "—"}</strong></span>
  <span class="badge">Activity: <strong>{gd['activity_final'] or "—"}</strong></span>
  <span class="badge">Genre: <strong>{gd['genre_final'] or "—"}</strong></span>
  {"<span class='badge'>No explicit</span>" if gd["exclude_explicit"] else ""}
</div>
""",
            unsafe_allow_html=True,
        )
        if gd.get("desc"):
            st.success(gd["desc"])

        # --- SAVE UI AT TOP ---
        default_title = " · ".join([x for x in [gd["mood_final"], gd["activity_final"], gd["genre_final"]] if x]) or "My Playlist"
        if "save_title" not in st.session_state:
            st.session_state.save_title = default_title

        st.subheader("Save this playlist")
        col_t, col_s = st.columns([3, 1])
        st.session_state.save_title = col_t.text_input(
            "Title",
            value=st.session_state.save_title,
            key="save_title_input",
            label_visibility="collapsed",
        )

        if col_s.button("Save", use_container_width=True, key="btn_save"):
            # normalize for storage (flatten 'track' dict)
            norm_tracks: List[Dict[str, Any]] = []
            for it in gd["items"]:
                tr = it.get("track") or {}
                norm_tracks.append({
                    "id": tr.get("id"),
                    "name": tr.get("name"),
                    "artists": [a.get("name","") for a in tr.get("artists", [])],
                    "album": (tr.get("album") or {}).get("name"),
                    "spotify_url": (tr.get("external_urls") or {}).get("spotify"),
                    "preview_url": tr.get("preview_url"),
                    "score": it.get("score"),
                    "reason": it.get("reason"),
                })

            meta = {
                "vibe_description": gd["vibe_description"],
                "mood": gd["mood_final"],
                "activity": gd["activity_final"],
                "genre_or_language": gd["genre_final"],
                "exclude_explicit": gd["exclude_explicit"],
                "limit": gd["limit"],
            }

            saved = save_playlist(
                title=st.session_state.save_title,
                request_meta=meta,
                tracks=norm_tracks,
                description=gd.get("desc") or "",
            )
            st.success(f"Saved (ID: {saved['id']})")
            st.session_state.selected_saved_id = saved["id"]

        # --- TRACKS BELOW ---
        render_tracks(gd["items"])

    else:
        empty_hint.info("Use the sidebar to describe your vibe and click Generate Playlist.")

# =============================
# Saved
# =============================
with tab_saved:
    st.subheader("Your saved playlists")
    rows = list_playlists()
    if not rows:
        st.info("No playlists saved yet.")
    else:
        fc1, fc2, fc3 = st.columns(3)
        f_mood = fc1.selectbox("Filter mood", ["All"] + sorted({r.get("mood") for r in rows if r.get("mood")}), index=0)
        f_activity = fc2.selectbox("Filter activity", ["All"] + sorted({r.get("activity") for r in rows if r.get("activity")}), index=0)
        f_genre = fc3.text_input("Filter genre contains", value="")

        def _keep(r: Dict[str, Any]) -> bool:
            if f_mood != "All" and r.get("mood") != f_mood:
                return False
            if f_activity != "All" and r.get("activity") != f_activity:
                return False
            if f_genre and f_genre.lower() not in (r.get("genre_or_language") or "").lower():
                return False
            return True

        view = [r for r in rows if _keep(r)]

        for row in view:
            with st.container():
                cA, cB, cC, cD = st.columns([4, 2, 2, 2])
                cA.markdown(f"**{row['title']}**")
                cB.markdown(f"Tracks: **{row['n_tracks']}**")
                cC.caption(f"{row.get('mood') or '—'} • {row.get('activity') or '—'}")
                cD.caption(row.get("created_at") or "")
                b1, b2, _ = st.columns([1, 1, 6])
                if b1.button("Open", key=f"open_{row['id']}"):
                    st.session_state.selected_saved_id = row["id"]
                if b2.button("Delete", key=f"del_{row['id']}"):
                    if delete_playlist(row["id"]):
                        st.warning("Deleted.")
                        st.rerun()
                    else:
                        st.error("Delete failed.")

                if st.session_state.selected_saved_id == row["id"]:
                    saved = load_playlist(row["id"]) or {}
                    desc = saved.get("description") or ""
                    tracks = saved.get("tracks", [])
                    if desc:
                        st.success(desc)
                    # reuse renderer for saved tracks (they're already flattened)
                    st.markdown('<div class="grid">', unsafe_allow_html=True)
                    for t in tracks:
                        tid = t.get("id")
                        if not tid:
                            continue
                        artists = ", ".join(t.get("artists", []))
                        score = t.get("score")
                        score_txt = "—" if score is None else f"{score:.2f}"
                        reason = t.get("reason") or ""
                        title = f"{t.get('name','Unknown')} — {artists}"
                        embed = f"https://open.spotify.com/embed/track/{tid}?utm_source=generator"
                        st.markdown(
                            f"""
<div class="card">
  <div class="track"><iframe src="{embed}" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe></div>
  <div class="card__body">
    <div class="card__title">{title}</div>
    <div class="meta">
      <span class="badge">score: {score_txt}</span>
      {"<span class='badge'>"+reason+"</span>" if reason else ""}
    </div>
  </div>
</div>
""",
                            unsafe_allow_html=True,
                        )
                    st.markdown("</div>", unsafe_allow_html=True)

# =============================
# About
# =============================
with tab_about:
    st.markdown("### What this app does")
    st.markdown(
        """
- Analyze your vibe via an NLP agent (`/analyze`) to infer mood and genre (optional).
- Combine your choices with auto-detected suggestions.
- Fetch & score tracks via `app.spotify.generate_playlist_from_user_settings(...)`.
- Explain the playlist using `generate_playlist_description(...)` (optional).
- Embed tracks and save to `.appdata/saved_playlists.json`. Open/Delete from the Saved tab.
"""
    )

# -----------------------------
# Footer
# -----------------------------
st.markdown("<div class='footer'>Built for your Agentic Music Recommender • Modern UI + Save/Load</div>", unsafe_allow_html=True)
