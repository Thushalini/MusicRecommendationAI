# pages/00_Landing.py
import os, streamlit as st
from dotenv import load_dotenv
import streamlit.components.v1 as components

# -----------------------------
# Env / Config
# -----------------------------
load_dotenv()
API_BASE     = os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL",     "http://127.0.0.1:8501")

st.set_page_config(page_title="Welcome • Login", page_icon="🎧", layout="centered")

# -----------------------------
# Header
# -----------------------------
st.markdown("""
<h1 style="margin-top:2rem;">Welcome</h1>
<p>Please sign in with your Spotify account to continue.</p>
""", unsafe_allow_html=True)

# -----------------------------
# Session fetch helper (auto redirect after login)
# -----------------------------
def inject_fetch_session():
    components.html(f"""
<html><body><script>
(async () => {{
  try {{
    // Try to fetch session if cookie exists (after OAuth)
    const resp = await fetch('{API_BASE}/spotify/session/me', {{
      credentials: 'include',
      headers: {{ 'Accept':'application/json' }}
    }});
    if (!resp.ok) return;
    const data = await resp.json();
    const token = data.access_token || '';
    const prof  = data.profile || {{}};

    if (token) {{
      const qp = new URLSearchParams(window.location.search);
      qp.set('spotify_token', token);
      qp.set('sp_name', encodeURIComponent(prof.display_name || ''));
      qp.set('sp_email', encodeURIComponent(prof.email || ''));
      const avatar = (prof.images && prof.images[0] && prof.images[0].url) || '';
      if (avatar) qp.set('sp_avatar', encodeURIComponent(avatar));
      // Redirect to home page (main app) with query params
      window.location.replace('{FRONTEND_URL}/?' + qp.toString());
    }}
  }} catch (e) {{
    console.error('session/me failed', e);
  }}
}})();
</script></body></html>
""", height=0)

inject_fetch_session()

# -----------------------------
# Login button as a TOP-LEVEL LINK (no iframe, no JS)
# -----------------------------
login_url = f"{API_BASE}/spotify/login"

# show the resolved URL (helps catch a blank/incorrect AGENTS_API_BASE)


st.markdown(
    f"""
    <div style="max-width:480px;margin-top:12px;">
      <a href="{login_url}" target="_self"
         style="display:inline-block;width:100%;text-align:center;padding:14px 18px;
                border-radius:12px;background:#1DB954;color:#000;font-weight:800;
                font-size:16px;text-decoration:none;cursor:pointer;">
        🎧 Sign in with Spotify
      </a>
    </div>
    """,
    unsafe_allow_html=True,
)


st.caption(
    "After you sign in on Spotify, you'll be returned here and automatically redirected to the home page."
)
