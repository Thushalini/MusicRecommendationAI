import streamlit as st

# --------- Page config ---------
st.set_page_config(page_title="Music Rec AI", page_icon="🎧", layout="wide")

# --------- Styles ---------
st.markdown("""
<style>
/* Page background */
.stApp {
  background: radial-gradient(1200px 600px at 10% 10%, rgba(29,185,84,0.18), transparent 60%),
              radial-gradient(1000px 500px at 90% 20%, rgba(0,255,255,0.10), transparent 60%),
              linear-gradient(180deg, #0e1116 0%, #0b0f14 100%);
  color: #e8eef7;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
}

/* Hide sidebar */
section[data-testid="stSidebar"] { display: none !important; }
button[kind="header"] { display: none !important; }

/* Main container */
div.block-container {
  padding-top: 2.5rem;
  padding-bottom: 2rem;
  max-width: 1200px;
}

/* Hero section */
.hero {
  text-align: center;
  padding: 1.8rem 1rem 1rem;
}
.hero h1 {
  font-size: clamp(28px, 5vw, 40px);
  line-height: 1.15;
  margin: 0 0 .5rem;
}
.hero p {
  font-size: clamp(14px, 2.4vw, 17px);
  color: #b7c2d0;
  margin: 0 auto;
  max-width: 700px;
}

/* Card layout */
.card {
  position: relative; /* for hover effects */
  overflow: hidden;   /* hide shine */
  background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 20px 18px 18px;
  backdrop-filter: blur(8px);
  box-shadow: 0 6px 22px rgba(0,0,0,.35);
  transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease, background .22s ease;
  text-align: center;
  height: 280px; /* reduced height */
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  will-change: transform, box-shadow;
}

/* Hover: lift + glow + subtle gradient pulse */
.card:hover {
  transform: translateY(-6px) scale(1.01);
  border-color: rgba(29,185,84,0.55);
  box-shadow:
    0 18px 48px rgba(0,0,0,.55),
    0 0 0 1px rgba(29,185,84,.25) inset,
    0 0 24px rgba(29,185,84,.18);
  background:
    radial-gradient(600px 280px at 10% -10%, rgba(29,185,84,0.14), transparent 60%),
    linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.03));
  cursor: pointer;
}

/* Hover: inner shine sweep */
.card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(75deg, transparent 40%, rgba(255,255,255,0.18) 50%, transparent 60%);
  transform: translateX(-120%);
  transition: transform .7s ease;
  pointer-events: none;
}
.card:hover::before {
  transform: translateX(120%);
}

/* Hover: soft outline aura */
.card::after {
  content: "";
  position: absolute;
  inset: -2px;
  border-radius: 18px;
  box-shadow: 0 0 0 0 rgba(29,185,84,.0);
  transition: box-shadow .25s ease;
  pointer-events: none;
}
.card:hover::after {
  box-shadow: 0 0 0 2px rgba(29,185,84,.18);
}

.card .head {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 6px;
}
.badge {
  font-size: 11px;
  text-transform: uppercase;
  color: #9dd8b0;
  background: rgba(29,185,84,0.12);
  border: 1px solid rgba(29,185,84,0.25);
  padding: 4px 8px;
  border-radius: 999px;
}
.icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: radial-gradient(180px 120px at 30% 20%, rgba(29,185,84,.35), rgba(29,185,84,.10));
  border: 1px solid rgba(255,255,255,0.10);
  font-size: 22px;
  transition: box-shadow .22s ease, transform .22s ease, border-color .22s ease;
}
/* Icon glow on hover */
.card:hover .icon {
  border-color: rgba(29,185,84,.45);
  box-shadow: inset 0 0 14px rgba(29,185,84,.25), 0 0 16px rgba(29,185,84,.25);
  transform: translateY(-1px);
}

/* Title & desc */
.card h3 {
  font-size: 19px;
  margin: 8px 0 4px;
  line-height: 1.2;
}
.card p {
  color: #b8c3d1;
  font-size: 14px;
  margin-bottom: 10px;
}

/* CTA Button */
.card .button-wrap {
  margin-top: 10px;
  display: flex;
  justify-content: center;
}
.card .btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 10px;
  border: 1px solid rgba(29,185,84,0.35);
  background: linear-gradient(180deg, rgba(29,185,84,0.4), rgba(29,185,84,0.18));
  color: #e9f6ed;
  font-weight: 600;
  text-decoration: none;
  transition: transform .15s ease, border-color .15s ease, background .15s ease, box-shadow .15s ease;
  font-size: 14px;
}
.card .btn:hover {
  transform: translateY(-2px);
  background: linear-gradient(180deg, rgba(29,185,84,0.5), rgba(29,185,84,0.22));
  box-shadow: 0 6px 16px rgba(0,0,0,.35), 0 0 0 1px rgba(29,185,84,.35) inset;
}
.small {
  font-size: 12px;
  color: #9aa7b7;
  margin-top: 6px;
}

/* Footer */
.footer {
  text-align: center;
  margin-top: 2rem;
  color: #95a3b4;
  font-size: 13px;
  opacity: .9;
}

/* Responsive */
@media (max-width: 900px) {
  .card { height: auto; margin-bottom: 1.5rem; }
}
</style>
""", unsafe_allow_html=True)

# --------- Hero ---------
st.markdown("""
<div class="hero">
  <div style="display:inline-grid;place-items:center;margin-bottom:10px;">
    <div class="icon" aria-hidden="true">🎧</div>
  </div>
  <h1>Welcome to <strong>Music Recommendation AI</strong></h1>
  <p>Discover playlists that fit your vibe. Start with a quick mood quiz or jump straight into playlist generation.<br/>
  Your Spotify-powered, Responsible-AI flavored music companion.</p>
</div>
""", unsafe_allow_html=True)

# --------- Two compact cards side-by-side ---------
c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown("""
<div class="card">
  <div>
    <div class="head">
      <div class="icon">❓</div>
      <span class="badge">Step 1</span>
    </div>
    <h3>Analyse your mood</h3>
    <p>Take a rapid valence–arousal quiz or type your feelings in natural language.<br/>We’ll fuse signals to infer your mood distribution.</p>
  </div>
  <div>
    <div class="button-wrap">
      <a href="/mood_ui" target="_self" class="btn">❓ Open Mood Quiz</a>
    </div>
    <div class="small">~30 seconds • improves recommendation accuracy</div>
  </div>
</div>
""", unsafe_allow_html=True)

with c2:
    st.markdown("""
<div class="card">
  <div>
    <div class="head">
      <div class="icon">🎵</div>
      <span class="badge">Step 2</span>
    </div>
    <h3>Build your playlist</h3>
    <p>Generate a personalized track list using your mood, text cues, and saved preferences.<br/>Export or save for later.</p>
  </div>
  <div>
    <div class="button-wrap">
      <a href="/streamlit_app" target="_self" class="btn">🎵 Go to Playlist Builder</a>
    </div>
    <div class="small">Uses your mood + text + history</div>
  </div>
</div>
""", unsafe_allow_html=True)

# --------- Footer ---------
st.markdown("""
<div class="footer">
  Tip: You can always return here from the top navigation. Enjoy the music! ✨
</div>
""", unsafe_allow_html=True)
