# app/mood_fusion_combined.py
# One-page Mood UI (free-text + signals + RG quiz) → POST /mood/fuse → redirect to streamlit_app.py

import os, json, requests, streamlit as st
from dotenv import load_dotenv
from typing import Any, Dict, Optional

# -----------------------------
# Env / config
# -----------------------------
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path, override=False)

API_BASE = os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000")
API_KEY  = os.getenv("AGENTS_API_KEY",  "dev-key-change-me")
HEADERS  = {"x-api-key": API_KEY}

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(page_title="Analyse your mood", page_icon="🎚️", layout="centered")

# -----------------------------
# Styles (centered, two-column layout, sleek panels)
# -----------------------------
st.markdown("""
<style>
:root { --primary:#1DB954; --bg:#0f1115; --panel:#141821; --muted:#9aa4b2; --text:#ecf1f8; }
.stApp {
  background:
    radial-gradient(1100px 700px at 15% -10%, #1db95422 0%, transparent 60%),
    radial-gradient(900px 500px at 110% 10%, #4776e633 0%, transparent 55%),
    var(--bg)!important;
  color: var(--text);
}
.block-container { padding-top: 1.6rem; max-width: 1100px; margin: 0 auto; }

/* Card shell */
.card{
  width:min(1060px,96vw);
  margin:18px auto;
  border:1px solid rgba(255,255,255,.08);
  background:linear-gradient(180deg,#161b25ee,#0f1115ee);
  border-radius:18px;
  box-shadow:0 10px 40px rgba(0,0,0,.35);
}
.card__head{ padding:18px 24px 0; text-align:center; }
.card__body{ padding:14px 24px 22px; }

/* Headings */
h1, h2, h3 { margin:0; }
.sub{ color:#9aa4b2; margin:6px 0 12px; text-align:center; }
hr{ border:none; border-top:1px solid rgba(255,255,255,.08); margin:10px 0 16px; }

/* Two columns wrapper */
.twocol {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  align-items: start;
}
@media (max-width: 900px){
  .twocol { grid-template-columns: 1fr; }
}

/* Panels */
.panel{
  border:1px solid rgba(255,255,255,.08);
  background:linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.02));
  border-radius:14px;
  padding:16px;
}
.panel h3 { text-align:center; margin-bottom:8px; }
.panel .hint{ color:#9aa4b2; font-size:13px; text-align:center; margin:-2px 0 10px; }

/* Buttons row */
.btnrow{ display:flex; justify-content:center; gap:12px; margin-top: 6px; }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Helpers
# -----------------------------
def seg(label: str, options: list[str], index: int = 0):
    try:
        return st.segmented_control(label, options, selection_mode="single")
    except Exception:
        return st.radio(label, options, index=index, horizontal=True)

def switch_to_playlist(mood_label: Optional[str]):
    # Save to session for streamlit_app.py
    if mood_label:
        st.session_state["fused_mood"] = {"label": mood_label}
        st.session_state["fused_mood_label"] = mood_label
    else:
        st.session_state.pop("fused_mood", None)
        st.session_state.pop("fused_mood_label", None)

    # Also expose as URL param (Streamlit ≥1.30 API; fallback for older)
    try:
        if mood_label: st.query_params["mood"] = mood_label
        else:          st.query_params.clear()
    except Exception:
        try:
            if mood_label: st.experimental_set_query_params(mood=mood_label)
            else:          st.experimental_set_query_params()
        except Exception:
            pass

    # Try to programmatically switch pages (Streamlit ≥1.27)
    for target in ("pages/streamlit_app.py", "streamlit_app.py"):
        try:
            st.switch_page(target)
            return
        except Exception:
            continue

    # Fallback: show a link the user can click
    st.success("Mood ready — open the playlist page to continue.")
    st.page_link("pages/streamlit_app.py", label="Go to main app ▶️", icon="🎵")

# -----------------------------
# UI
# -----------------------------
st.markdown('<div class="card"><div class="card__head">', unsafe_allow_html=True)
st.markdown("## Analyse your mood", unsafe_allow_html=True)
st.markdown("<p class='sub'>Describe your vibe, add signals, and (optionally) answer the 10-item quiz.</p>", unsafe_allow_html=True)
st.markdown('</div><div class="card__body">', unsafe_allow_html=True)

OPT = {"Strongly Agree":"SA","Agree":"A","Can't Say":"CS","Disagree":"D","Strongly Disagree":"SD"}

with st.form("mood_all", clear_on_submit=False):
    # ---------------- Two columns ----------------
    st.markdown('<div class="twocol">', unsafe_allow_html=True)

    # LEFT: Free text + signals + SAM + context
    with st.container():
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<h3>Your Vibe & Signals</h3><div class="hint">Free text + quick selectors</div>', unsafe_allow_html=True)

        txt = st.text_area(
            "1) In your own words, how do you feel right now?",
            value=st.session_state.get("vibe_prefill", ""),
            placeholder="e.g., It's been a long day but I'm hopeful.",
            height=110,
        )
        st.markdown("---")

        c1, c2 = st.columns(2)
        with c1:
            color = seg("2) Pick a color", ["Yellow","Green","Red","Blue","Purple","Orange","Black","White"])
        with c2:
            emoji = seg("3) Pick an emoji", ["😄","🙂","😠","😢","💪","😴"])

        st.markdown("**4) Self-Assessment Manikin (SAM)**")
        valence = st.slider("Valence (unpleasant → pleasant)", 0.0, 1.0, 0.6, 0.05)
        arousal = st.slider("Arousal (calm → excited)", 0.0, 1.0, 0.6, 0.05)

        g1, g2, g3 = st.columns(3)
        with g1: energy = st.selectbox("Energy", ["low","medium","high"], index=1)
        with g2: social = st.selectbox("Company", ["solo","group"], index=0)
        with g3: focus  = st.selectbox("Focus",  ["relax","party","gym","study"], index=0)

        st.markdown('</div>', unsafe_allow_html=True)

    # RIGHT: 10-item mood quiz (+ debug toggle)
    with st.container():
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<h3>10-Item Mood Quiz</h3><div class="hint">Optional but improves accuracy</div>', unsafe_allow_html=True)

        q1 = st.radio("1) I don't feel like doing anything.",  list(OPT), horizontal=True)
        q2 = st.radio("2) I am feeling bored.",                 list(OPT), horizontal=True)
        q3 = st.radio("3) Nothing seems fun anymore.",          list(OPT), horizontal=True)
        q4 = st.radio("4) I find beauty in things around me.",  list(OPT), horizontal=True)
        q5 = st.radio("5) I feel loved.",                       list(OPT), horizontal=True)
        q6 = st.radio("6) I’ve been feeling confident.",        list(OPT), horizontal=True)
        q7 = st.radio("7) My efforts aren’t appreciated.",      list(OPT), horizontal=True)
        q8 = st.radio("8) I completed today’s agenda.",         list(OPT), horizontal=True)
        q9 = st.radio("9) I get irritated easily.",             list(OPT), horizontal=True)
        q10 = st.radio("10) Recently, I have trouble concentrating (focus override).", ["No","Yes"], index=0, horizontal=True)

        st.markdown('---', unsafe_allow_html=True)
        show_debug = st.checkbox("Show raw JSON", value=False)

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # /twocol

    # Buttons centered under both columns
    st.markdown('<div class="btnrow">', unsafe_allow_html=True)
    colA, colB = st.columns([1,1])
    with colA:
        skip = st.form_submit_button("Skip")
    with colB:
        go = st.form_submit_button("Analyse & Continue")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("</div></div>", unsafe_allow_html=True)

# -----------------------------
# Actions
# -----------------------------
if skip:
    switch_to_playlist(None)

if go:
    payload: Dict[str, Any] = {
        "text": txt or "",
        "color": color,
        "emoji": emoji,
        "valence": float(valence),
        "arousal": float(arousal),
        "quiz": {
            # lightweight context prefs used by your builder
            "energy": energy, "social": social, "focus": focus,
            # RG 10-item block (backend can ignore if not used)
            "q1": OPT[q1], "q2": OPT[q2], "q3": OPT[q3], "q4": OPT[q4], "q5": OPT[q5],
            "q6": OPT[q6], "q7": OPT[q7], "q8": OPT[q8], "q9": OPT[q9],
            "q10": "yes" if q10 == "Yes" else "no",
        },
    }

    with st.status("Fusing mood signals…", expanded=True) as s:
        try:
            r = requests.post(f"{API_BASE}/mood/fuse", headers=HEADERS, json=payload, timeout=20)
            s.write("POST /mood/fuse")
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            st.error(f"API error: {e}")
            st.stop()

        final = (data.get("final") or {})
        label = (final.get("label") or "").strip()
        conf  = float(final.get("confidence") or 0.0)

        # Persist for playlist page
        st.session_state["mood_fuse"] = data
        st.session_state["fused_mood"] = final
        st.session_state["fused_mood_label"] = label
        st.session_state["fused_mood_conf"]  = round(conf, 3)
        st.session_state["vibe_prefill"]     = txt or ""

        s.update(label=f"Mood fusion complete • {label or '—'} (conf {conf:.2f})", state="complete", expanded=False)

    if show_debug:
        st.markdown("#### Raw response")
        st.code(json.dumps(st.session_state["mood_fuse"], indent=2), language="json")

    st.toast(f"Mood: {label or '—'}")
    switch_to_playlist(label or None)
