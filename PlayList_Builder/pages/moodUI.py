# app/mood_fusion_ui.py
# Centered "Analyse your mood" card → POST /mood/fuse → redirect to streamlit_app.py
# Single button row inside the form (no duplicate footer), presets removed.

import os
import json
import requests
import streamlit as st
from typing import Any, Dict, Optional
from dotenv import load_dotenv


# -----------------------------
# Env / config
# -----------------------------
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path, override=False)

API_BASE = os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000")
API_KEY  = os.getenv("AGENTS_API_KEY",  "dev-key-change-me")

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(page_title="Analyse your mood", page_icon="🎚️", layout="centered")

# -----------------------------
# Styles (centered card UI)
# -----------------------------
st.markdown("""
<style>
/* Hide only unwanted page links in the sidebar nav */
div[data-testid="stSidebarNav"] li a[href*="Main"] {display: none !important;}
div[data-testid="stSidebarNav"] li a[href*="streamlit_app"] {display: none !important;}

/* Optional: adjust top padding for a cleaner look */
section[data-testid="stSidebar"] > div:first-child {padding-top: 0 !important;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
:root {
  --primary:#1DB954; --bg:#0f1115; --panel:#141821;
  --muted:#9aa4b2; --text:#ecf1f8; --radius:16px;
}

/* Remove Streamlit’s default top padding */
[data-testid="stAppViewContainer"] > .main,
.block-container { padding-top: 0 !important; }

/* Background and text colors */
.stApp {
  background: radial-gradient(1100px 700px at 15% -10%, #1db95422 0%, transparent 60%),
              radial-gradient(900px 500px at 110% 10%, #4776e633 0%, transparent 55%),
              var(--bg)!important;
  color: var(--text);
}

/* Center container closer to top */
.center-wrap {
  min-height: auto;
  display: block;
  padding: 32px 24px 40px;
}

/* Card styling */
.card {
  width: min(880px, 92vw);
  border: 1px solid rgba(255,255,255,.08);
  background: linear-gradient(180deg,#161b25ee,#0f1115ee);
  border-radius: var(--radius);
  box-shadow: 0 10px 40px rgba(0,0,0,.35);
  backdrop-filter: blur(8px);
  margin: 0 auto;
}
.card__head { padding: 16px 24px 0; }
.card__body { padding: 8px 24px 20px; }

/* Typography */
h1 {
  font-size: clamp(1.4rem, 2.3vw, 2.1rem);
  margin: 0 0 6px 0;
  letter-spacing:.3px;
}
.sub { color: var(--muted); margin: 0 0 10px 0; }
hr { border: none; border-top:1px solid rgba(255,255,255,.08); margin: 10px 0 18px; }

/* Inputs + Buttons */
.stTextArea textarea, .stSelectbox div[data-baseweb="select"]>div,
.stSlider, .stRadio, .stSegmentedControl, .stTextInput input {
  background: rgba(255,255,255,.03)!important;
  color: var(--text)!important;
  border-radius: 12px!important;
}
.stButton button{
  background:var(--primary)!important;
  color:#000!important;
  font-weight:700!important;
  border-radius:12px!important;
  padding:10px 16px!important;
  border:none!important;
  transition:transform .08s ease, box-shadow .08s ease;
}
.stButton button:hover{ transform:translateY(-1px); box-shadow:0 8px 24px #1db95433; }

/* Misc elements */
.linky { background:transparent!important; color:var(--text)!important;
         border:1px solid rgba(255,255,255,.14)!important; }
.badges{ display:flex; gap:.4rem; flex-wrap:wrap; }
.badge{ display:inline-flex; align-items:center; gap:.35rem;
        border:1px solid rgba(255,255,255,.08); color:var(--muted);
        padding:.30rem .55rem; border-radius:999px;
        font-size:.85rem; background:linear-gradient(180deg,#151924,#0f1115); }
</style>
""", unsafe_allow_html=True)


# -----------------------------
# Helpers
# -----------------------------
def post_fuse(payload: Dict[str, Any]) -> Optional[dict]:
    try:
        r = requests.post(
            f"{API_BASE}/mood/fuse",
            json=payload,
            headers={"x-api-key": API_KEY},
            timeout=15,
        )
        if not r.ok:
            st.error(f"API {r.status_code}: {r.text}")
            return None
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None

def seg(label: str, options: list[str], default_index: int = 0):
    try:
        return st.segmented_control(label, options, selection_mode="single")
    except Exception:
        return st.radio(label, options, index=default_index, horizontal=True)

def _go_to_streamlit_app(mood_label: Optional[str] = None):
    # Store in session for the playlist page to consume
    if mood_label:
        st.session_state["fused_mood"] = mood_label
    else:
        st.session_state.pop("fused_mood", None)

    # Also set a URL param for optional retrieval in streamlit_app.py
    if mood_label:
        st.query_params["mood"] = mood_label
    else:
        st.query_params.clear()

    # Try multiple targets; fall back to a message if switch_page isn't available
    targets = [
        "app/streamlit_app.py",          
        "streamlit_app.py",           
        "pages/streamlit_app.py",         
    ]
    for t in targets:
        try:
            st.switch_page(t)  # Streamlit ≥1.27
            return
        except Exception:
            continue

    st.success("Ready! Open the playlist page to continue.")
    st.stop()

# -----------------------------
# Centered Card with Questions
# -----------------------------
st.markdown('<div class="center-wrap">', unsafe_allow_html=True)
st.markdown('<div class="card">', unsafe_allow_html=True)

st.markdown('<div class="card__head">', unsafe_allow_html=True)
st.markdown("<h1>Analyse your mood</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub'>Answer a few quick questions. You can also skip and choose later.</p>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="card__body">', unsafe_allow_html=True)

# SINGLE form with ONE button row (no footer duplicates, no presets above the text box)
with st.form("mood_form", clear_on_submit=False):
    txt = st.text_area(
        "1) In your own words, how do you feel right now?",
        value="",
        placeholder="e.g., It's been a long day but I'm hopeful.",
        height=110,
    )
    st.markdown("---")

    cols = st.columns(2)
    with cols[0]:
        color = seg("2) Pick a color that matches your current mood",
                    ["Yellow","Green","Red","Blue","Purple","Orange","Black","White"])
    with cols[1]:
        emoji = seg("3) Choose an emoji that fits now", ["😄","🙂","😠","😢","💪","😴"])

    st.markdown("---")

    st.markdown("**4) Self-Assessment Manikin (SAM)**")
    valence = st.slider("Valence (unpleasant → pleasant)", 0.0, 1.0, 0.6, 0.05)
    arousal = st.slider("Arousal (calm → excited)", 0.0, 1.0, 0.6, 0.05)

    q1, q2, q3 = st.columns(3)
    with q1:
        energy = st.selectbox("Energy", ["low","medium","high"], index=1)
    with q2:
        social = st.selectbox("Company", ["solo","group"], index=0)
    with q3:
        focus  = st.selectbox("Focus",  ["relax","party","gym","study"], index=0)

    show_debug = st.checkbox("Show raw JSON", value=False)

    colA, colB = st.columns([1,1])
    with colA:
        submitted_skip = st.form_submit_button("Skip")
    with colB:
        submitted_analyse = st.form_submit_button("Analyse & continue")

st.markdown("</div>", unsafe_allow_html=True)   # .card__body
st.markdown("</div>", unsafe_allow_html=True)   # .card
st.markdown("</div>", unsafe_allow_html=True)   # .center-wrap

# -----------------------------
# Actions (single button row)
# -----------------------------
if submitted_skip:
    _go_to_streamlit_app(None)

if submitted_analyse:
    with st.status("Fusing mood signals…", expanded=True) as s:
        payload = {
            "text": txt or "",
            "color": color,
            "emoji": emoji,
            "valence": float(valence),
            "arousal": float(arousal),
            "quiz": {"energy": energy, "social": social, "focus": focus},
        }
        s.write("Sending inputs to FastAPI (`POST /mood/fuse`)")
        data = post_fuse(payload)
        if not data:
            st.stop()

        final = (data.get("final") or {})
        label = final.get("label") or ""
        conf  = float(final.get("confidence") or 0.0)

        st.session_state["mood_fuse"] = data
        st.session_state["fused_mood"] = label
        st.session_state["vibe_prefill"] = txt or ""

        s.update(label=f"Mood fusion complete • Final: {label or '—'} (conf {conf:.2f})", state="complete", expanded=False)

    if show_debug:
        st.markdown("#### Raw response")
        st.code(json.dumps(st.session_state["mood_fuse"], indent=2), language="json")

    st.toast(f"Mood detected: {label or '—'}")
    _go_to_streamlit_app(label or None)

# -----------------------------
# NOTE for streamlit_app.py
# -----------------------------
# In your streamlit_app.py (playlist page), read the mood like this:
#
#   fused = st.session_state.get("fused_mood")
#   try:
#       qp = st.query_params.get("mood")  # Streamlit ≥1.30
#   except Exception:
#       qp = st.experimental_get_query_params().get("mood", [None])[0]
#   mood = fused or qp
#   # Use `mood` wherever your existing "mood" filter/selectbox lives.
