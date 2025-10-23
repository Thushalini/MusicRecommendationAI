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
  position: relative;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 20px 18px 18px;
  backdrop-filter: blur(8px);
  box-shadow: 0 6px 22px rgba(0,0,0,.35);
  transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease, background .22s ease;
  text-align: center;
  height: 280px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  will-change: transform, box-shadow;
}
.card:hover {
  transform: translateY(-6px) scale(1.01);
  border-color: rgba(29,185,84,0.55);
  box-shadow: 0 18px 48px rgba(0,0,0,.55),
              0 0 0 1px rgba(29,185,84,.25) inset,
              0 0 24px rgba(29,185,84,.18);
  background: radial-gradient(600px 280px at 10% -10%, rgba(29,185,84,0.14), transparent 60%),
              linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.03));
  cursor: pointer;
}
.card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(75deg, transparent 40%, rgba(255,255,255,0.18) 50%, transparent 60%);
  transform: translateX(-120%);
  transition: transform .7s ease;
  pointer-events: none;
}
.card:hover::before { transform: translateX(120%); }
.card::after {
  content: "";
  position: absolute;
  inset: -2px;
  border-radius: 18px;
  box-shadow: 0 0 0 0 rgba(29,185,84,.0);
  transition: box-shadow .25s ease;
  pointer-events: none;
}
.card:hover::after { box-shadow: 0 0 0 2px rgba(29,185,84,.18); }

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
.card:hover .icon {
  border-color: rgba(29,185,84,.45);
  box-shadow: inset 0 0 14px rgba(29,185,84,.25), 0 0 16px rgba(29,185,84,.25);
  transform: translateY(-1px);
}

.card h3 { font-size: 19px; margin: 8px 0 4px; line-height: 1.2; }
.card p { color: #b8c3d1; font-size: 14px; margin-bottom: 10px; }
.card .button-wrap { margin-top: 10px; display: flex; justify-content: center; }
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
  font-size: 14px;
  transition: transform .15s ease, border-color .15s ease, background .15s ease, box-shadow .15s ease;
}
.card .btn:hover {
  transform: translateY(-2px);
  background: linear-gradient(180deg, rgba(29,185,84,0.5), rgba(29,185,84,0.22));
  box-shadow: 0 6px 16px rgba(0,0,0,.35), 0 0 0 1px rgba(29,185,84,.35) inset;
}
.small { font-size: 12px; color: #9aa7b7; margin-top: 6px; }

/* Pricing grid */
.pricing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  margin-top: 22px;
}
.plan-card { text-align: left; height: auto; padding: 24px 20px; }
.plan-card h3 { margin: 0 0 6px; font-size: 20px; }
.plan-card .subtitle { font-size: 11px; color: #9aa7b7; text-transform: uppercase; letter-spacing: .4px; margin-bottom: 6px; }
.plan-card .price { color: #9dd8b0; font-weight: 600; margin: 6px 0 10px; }
.plan-card ul { margin: 0; padding-left: 18px; color: #c8d3e1; font-size: 14px; }
.plan-card ul li { margin: 8px 0; }
.plan-card .strike { text-decoration: line-through; opacity: .55; margin-right: 8px; }
.plan-highlight { border-color: rgba(29,185,84,0.55) !important; box-shadow: 0 0 0 1px rgba(29,185,84,.28) inset; }

.footer {
  text-align: center;
  margin-top: 2rem;
  color: #95a3b4;
  font-size: 13px;
  opacity: .9;
}
</style>
""", unsafe_allow_html=True)

# --------- Hero Section ---------
st.markdown("""
<div class="hero">
  <div style="display:inline-grid;place-items:center;margin-bottom:10px;">
    <div class="icon" aria-hidden="true">🎧</div>
  </div>
  <h1>Welcome to <strong>Music Recommendation AI</strong></h1>
  <p>Discover playlists that fit your vibe. Start with a quick mood quiz or jump straight into playlist generation.<br/>
  Your Spotify-powered, intelligent playlist companion.</p>
</div>
""", unsafe_allow_html=True)

# --------- Feature Cards ---------
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
    <div class="button-wrap"><a href="/mood_ui" target="_self" class="btn">Open Mood Quiz</a></div>
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
    <div class="button-wrap"><a href="/streamlit_app" target="_self" class="btn">Go to Playlist Builder</a></div>
    <div class="small">Uses your mood + text + history</div>
  </div>
</div>
""", unsafe_allow_html=True)

# --------- Pricing Section ---------
st.markdown('<div style="text-align:center;margin-top:2.2rem;"><h2>Pricing Model</h2></div>', unsafe_allow_html=True)
billing_yearly = st.toggle("Yearly billing (save ~25%)", value=False)

monthly_price = 1490
yearly_price = 13400
student_price = 590
b2b_low, b2b_high = 45000, 75000

if billing_yearly:
    main_price = f"LKR {yearly_price:,} / year"
    strike = f"<span class='strike'>LKR {int(yearly_price*1.25):,} / year</span>"
else:
    main_price = f"LKR {monthly_price:,} / month"
    strike = f"<span class='strike'>LKR {int(monthly_price*1.25):,} / month</span>"

st.markdown(f"""
<div style="text-align:center;color:#9aa7b7;margin-top:6px;">
  Flexible plans for individuals and businesses. Toggle billing to preview prices.
</div>

<div class="pricing-grid">

  <div class="card plan-card">
    <div class="subtitle">Starter</div>
    <h3>Free Tier</h3>
    <p class="price">LKR 0 / month</p>
    <ul>
      <li>Basic mood detection & playlist generation</li>
      <li>Up to 10 tracks per playlist</li>
      <li>Core moods only (happy, chill, sad, workout)</li>
      <li>Non-sensitive analytics</li>
    </ul>
    <div class="button-wrap" style="justify-content:flex-start;">
      <a href="#" class="btn">Get Free</a>
    </div>
  </div>

  <div class="card plan-card plan-highlight">
    <div class="subtitle">Most Popular</div>
    <h3>Premium</h3>
    <p class="price">{strike} {main_price}</p>
    <ul>
      <li>Advanced mood fusion (text + quiz)</li>
      <li>Unlimited playlist creation</li>
      <li>Personalized recommendations (“For You”)</li>
      <li>Export to Spotify / YouTube Music</li>
      <li>Mood-tracking dashboard</li>
      <li>Student plan: LKR {student_price:,} / month</li>
    </ul>
    <div class="button-wrap" style="justify-content:flex-start;">
      <a href="#" class="btn">Upgrade to Premium</a>
    </div>
  </div>

  <div class="card plan-card">
    <div class="subtitle">For Teams</div>
    <h3>Enterprise / B2B</h3>
    <p class="price">LKR {b2b_low:,} – LKR {b2b_high:,} / year</p>
    <ul>
      <li>AI API access for partners</li>
      <li>Auto-curated playlists by mood/time-of-day</li>
      <li>Integrations for cafes, gyms, events</li>
      <li>Custom branding & SLA options</li>
      <li>Business analytics & support</li>
      <li>Privacy-safe, scalable deployment</li>
    </ul>
    <div class="button-wrap" style="justify-content:flex-start;">
      <a href="#" class="btn">Contact Sales</a>
    </div>
  </div>

</div>

<div style="margin-top:1.2rem;text-align:center;color:#9aa7b7;font-size:14px;">
  ✓ Our hybrid model combines <b>Freemium onboarding</b>, <b>affordable subscriptions</b>, and <b>B2B licensing</b> — ensuring accessibility and scalability.
</div>
""", unsafe_allow_html=True)

# --------- Responsible AI Dropdown ---------
with st.expander("🛡️ Responsible AI Principles Used in Our System"):
    st.markdown("""
Our Music Recommendation AI system is designed with Responsible AI principles deeply integrated across all three agents — **Mood Detector**, **Genre Classifier**, and **Playlist Builder**.  
We ensure that the system behaves ethically, transparently, and respects user autonomy at every stage.

**1. Ethical Data Usage and Privacy Protection**  
- The system only uses user-provided inputs (mood text or quiz responses) and Spotify’s public metadata (like tempo, energy, and valence).  
- No personal or sensitive data is stored or shared; Spotify tokens are securely handled through OAuth and automatically refreshed.  
- This follows the principle of data minimization, ensuring privacy and confidentiality.

**2. Fairness and Non-Discrimination**  
- Mood and genre predictions are purely content-based, relying only on emotions and audio features — not race, gender, or location.  
- This reduces algorithmic bias and ensures fairness, equality, and inclusivity.

**3. Transparency and Explainability**  
- The system provides clear reasoning behind each recommendation.  
  _Example: “Songs were chosen because your detected mood is ‘chill’ with medium energy and positive valence.”_  
- This transparency builds user trust.

**4. User Autonomy and Consent**  
- Users have full control over their experience — they can choose to describe their mood, take the quiz, or regenerate playlists anytime.  
- This supports human-in-the-loop decision-making, keeping the final choice with the user.

**5. Well-being and Emotional Awareness**  
- The system is sensitive to user moods. It avoids recommending aggressive or explicit tracks when users feel sad or calm.  
- This promotes emotional well-being and prevents negative psychological impacts.

✅ **Summary:**  
Our system integrates Responsible AI by ensuring fairness, transparency, privacy, and user control.  
Every agent operates under ethical guidelines to create emotionally appropriate, bias-free, and privacy-respecting music recommendations — promoting trust and well-being for all users.
""")

# --------- Footer ---------
st.markdown("""
<div class="footer">
  © 2025 Music Recommendation AI — Empowering mood-based discovery.
</div>
""", unsafe_allow_html=True)
