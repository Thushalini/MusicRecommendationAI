# streamlit run app/moodUI.py
# Modern UI + FastAPI-connected Mood Fusion (/mood/fuse)
import os
import json
import requests
import streamlit as st
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# -----------------------------
# Env / config (same pattern)
# -----------------------------
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path, override=False)

API_BASE = os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000")
API_KEY  = os.getenv("AGENTS_API_KEY",  "dev-key-change-me")

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="Mood Activities",
    page_icon="🎚️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Styles (mirrors streamlit_app look)
# -----------------------------
st.markdown(
    """
<style>
:root {
  --primary:#1DB954; --bg:#0f1115; --panel:#141821; --card:#141821cc;
  --muted:#9aa4b2; --text:#ecf1f8; --border:1px solid rgba(255,255,255,.08); --radius:16px;
}

.stApp {
  background: radial-gradient(1000px 600px at 10% -10%, #1db95422 0%, transparent 60%),
              radial-gradient(800px 400px at 110% 10%, #4776e633 0%, transparent 55%),
              var(--bg) !important; color:var(--text);
}

section[data-testid="stSidebar"] { background: linear-gradient(180deg,#12151c,#0f1115)!important; border-right:var(--border); }
section[data-testid="stSidebar"] .stMarkdown, section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label { color:var(--muted)!important; }

.hero{ border:var(--border); background:linear-gradient(180deg,#141821dd,#0f1115cc); backdrop-filter:blur(8px);
       border-radius:var(--radius); padding:20px 24px; }
.hero h1{ margin:0 0 6px 0; font-size:clamp(1.4rem,2.2vw,2.1rem); letter-spacing:.3px; }
.hero p{ margin:0; color:var(--muted); }

.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"]>div, .stNumberInput input,
.stMultiSelect div[data-baseweb="select"]>div, .stSlider, .stRadio, .stSegmentedControl {
  background: rgba(255,255,255,.02)!important; color:var(--text)!important;
}
.stTextInput input, .stTextArea textarea { border:var(--border)!important; border-radius:12px!important; }

.stButton button{
  background:var(--primary)!important; color:#000000!important; font-weight:700!important; border-radius:12px!important;
  padding:10px 16px!important; border:none!important; transition:transform .08s ease, box-shadow .08s ease;
}
.stButton button:hover{ transform:translateY(-1px); box-shadow:0 8px 24px #1db95433; }
.stButton button:active{ transform:translateY(0) scale(.99); }

.badges{ display:flex; flex-wrap:wrap; gap:.4rem; margin:.3rem 0 .2rem; }
.badge{ display:inline-flex; align-items:center; gap:.35rem; border:var(--border); color:var(--muted);
        padding:.30rem .55rem; border-radius:999px; font-size:.85rem; background:linear-gradient(180deg,#151924,#0f1115); }

.card{ border:var(--border); background:var(--card); border-radius:16px; overflow:hidden; }
.card__body{ padding:14px 16px 16px; }
.card__title{ margin:.2rem 0 .55rem; font-size:15px; font-weight:700; letter-spacing:.2px; }
.footer{ color:var(--muted); font-size:13px; text-align:center; padding:16px 0 6px; opacity:.9; }
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Helpers (same API calling pattern)
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
    # segmented_control with graceful fallback to radio (like your draft)
    try:
        return st.segmented_control(label, options, selection_mode="single")
    except Exception:
        return st.radio(label, options, index=default_index, horizontal=True)

# -----------------------------
# Layout Header
# -----------------------------
left, right = st.columns([1, 2.2])
with left:
    st.markdown(
        """
<div class="hero">
  <h1>Mood Activities</h1>
  <p>Blend <b>text mood</b> with <b>simple self-reports</b> (color, emoji, SAM sliders)
  and send a fused mood to downstream agents.</p>
</div>
""",
        unsafe_allow_html=True,
    )

with right:
    st.markdown("### Quick presets")
    c1, c2, c3 = st.columns(3)
    if c1.button("Calm focus"):
        st.session_state.vibe_prefill = "It's been a long day but I'm hopeful and calm."
        st.session_state.pref_color = "Blue"
        st.session_state.pref_emoji = "🙂"
    if c2.button("Energetic gym"):
        st.session_state.vibe_prefill = "Pumped for a workout, need hype tracks."
        st.session_state.pref_color = "Red"
        st.session_state.pref_emoji = "💪"
    if c3.button("Sleepy & soft"):
        st.session_state.vibe_prefill = "Sleepy, want soft music and low energy."
        st.session_state.pref_color = "Purple"
        st.session_state.pref_emoji = "😴"

# -----------------------------
# Sidebar Controls (consistent feel)
# -----------------------------
with st.sidebar:
    st.subheader("Your inputs")

    txt = st.text_area(
        "Say a few words about your vibe",
        value=st.session_state.get("vibe_prefill", ""),
        placeholder="e.g., It's been a long day but I'm hopeful.",
        height=110,
    )

    color = seg("Color", ["Yellow","Green","Red","Blue","Purple","Orange","Black","White"])
    if "pref_color" in st.session_state:
        color = st.session_state.pop("pref_color")

    emoji = seg("Emoji", ["😄","🙂","😠","😢","💪","😴"])
    if "pref_emoji" in st.session_state:
        emoji = st.session_state.pop("pref_emoji")

    st.markdown("**Self-Assessment (SAM)**")
    valence = st.slider("Valence (unpleasant → pleasant)", 0.0, 1.0, 0.6, 0.05)
    arousal = st.slider("Arousal (calm → excited)", 0.0, 1.0, 0.6, 0.05)

    col1, col2, col3 = st.columns(3)
    with col1:
        energy = st.selectbox("Energy", ["low","medium","high"], index=1)
    with col2:
        social = st.selectbox("Company", ["solo","group"], index=0)
    with col3:
        focus  = st.selectbox("Focus",  ["relax","party","gym","study"], index=0)

    show_debug = st.checkbox("Show raw JSON", value=False)
    go = st.button("Analyze & Fuse", use_container_width=True)

# -----------------------------
# Main tabs (Results / About)
# -----------------------------
tab_results, tab_about = st.tabs(["Results", "How it works"])

with tab_results:
    if go:
        # modern step status (same pattern)
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

        payload = {
            "text": txt or "",
            "color": color,
            "emoji": emoji,
            "valence": float(valence),
            "arousal": float(arousal),
            "quiz": {"energy": energy, "social": social, "focus": focus},
        }

        with mk_status("Fusing mood signals") as s:
            s.write("Step 1 • Sending inputs to FastAPI (`/mood/fuse`)")
            data = post_fuse(payload)
            if not data:
                st.stop()

            s.update(label="Fusing mood signals • Aggregating model + priors")
            # Persist for rerender if needed
            st.session_state.mood_fuse = data

            try:
                s.update(label="Mood fusion complete", state="complete", expanded=False)
            except Exception:
                pass

        st.toast("Mood fused.")

    # Render block
    data = st.session_state.get("mood_fuse")
    if data:
        # badges
        final = data.get("final", {}) or {}
        st.markdown(
            f"""
<div class="badges">
  <span class="badge">Final: <strong>{final.get('label','—')}</strong></span>
  <span class="badge">Confidence: <strong>{final.get('confidence',0.0):.2f}</strong></span>
</div>
""",
            unsafe_allow_html=True,
        )

        # final card
        with st.container():
            st.markdown('<div class="card"><div class="card__body">', unsafe_allow_html=True)
            st.markdown("#### Final Mood")
            st.write(f"**{final.get('label','—')}**  (conf: {final.get('confidence',0.0):.2f})")
            if isinstance(final.get("scores"), dict) and final["scores"]:
                st.json(final["scores"])
            st.markdown("</div></div>", unsafe_allow_html=True)

        # text model block
        text_block = data.get("text", {}) or {}
        with st.container():
            st.markdown('<div class="card"><div class="card__body">', unsafe_allow_html=True)
            st.markdown("#### Text Model")
            st.write(f"**{text_block.get('label','—')}**  (conf: {text_block.get('confidence',0.0):.2f})")
            if isinstance(text_block.get("scores"), dict) and text_block["scores"]:
                st.json(text_block["scores"])
            st.markdown("</div></div>", unsafe_allow_html=True)

        # activity signals block
        with st.container():
            st.markdown('<div class="card"><div class="card__body">', unsafe_allow_html=True)
            st.markdown("#### Activity Signals (priors)")
            st.json(data.get("signals", {}) or {})
            st.markdown("</div></div>", unsafe_allow_html=True)

        if show_debug:
            st.markdown("#### Raw response")
            st.code(json.dumps(data, indent=2), language="json")

    else:
        st.info("Use the sidebar to input your mood signals, then click **Analyze & Fuse**.")

with tab_about:
    st.markdown("### What this page does")
    st.markdown(
        """
- Collects **text** + **simple activities** (color, emoji, SAM sliders, quiz).
- Sends them to **FastAPI** at `POST /mood/fuse` with header `x-api-key`.
- Displays **Text Model** result, **Activity Signals**, and the **Final fused mood** (label + confidence).
- The fused mood is ready to forward to the Genre/Playlist builder agents.
        """
    )

# -----------------------------
# Footer
# -----------------------------
st.markdown("<div class='footer'>Agentic Music Recommender • Mood Fusion UI</div>", unsafe_allow_html=True)
