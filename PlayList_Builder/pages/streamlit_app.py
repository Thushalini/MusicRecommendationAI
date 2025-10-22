# streamlit_app.py
# Modern UI + Persistent generated playlist + Save/Load to .appdata/saved_playlists.json
# Replaced Spotify OAuth with local Streamlit login/signup (app/auth_local.py)

import os, sys, json, requests, streamlit as st
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

# --- make project root importable (so 'app' package resolves) ---
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.spotify import generate_playlist_from_user_settings           # UNCHANGED
from app.llm_helper import generate_playlist_description              # UNCHANGED
from app.datastore import save_playlist, list_playlists, load_playlist, delete_playlist  # UNCHANGED

import streamlit.components.v1 as components  

# -----------------------------
# Env / config
# -----------------------------
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path, override=False)

API_BASE = os.getenv("AGENTS_API_BASE", "http://127.0.0.1:8000")
API_KEY  = os.getenv("AGENTS_API_KEY",  "dev-key-change-me")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:8501")
def _h(): return {"x-api-key": API_KEY}


# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="Music Recommendation AI",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Handle OAuth redirect / hydrate session_state ---


# use the stable API (and after set_page_config)
_q = st.query_params
# Direct token in URL (DEV only)
if _q.get("spotify_token"):
    st.session_state["spotify_access_token"] = _q["spotify_token"][0]
    
    avatar_raw = _q.get("sp_avatar", [""])[0] if _q.get("sp_avatar") else ""
    avatar_url = unquote(avatar_raw) if avatar_raw else ""
    st.session_state["spotify_profile"] = {
        "display_name": _q.get("sp_name", [""])[0],
        "email": _q.get("sp_email", [""])[0],
        "images": [{"url": avatar_url}] if avatar_url else [],
    }
# Or sid + fetch_session -> call backend to get token/profile
elif _q.get("sid") and _q.get("fetch_session", ["0"])[0] == "1":
    sid = _q["sid"][0]
    try:
        resp = requests.get(f"{API_BASE}/spotify/session/by_sid", params={"sid": sid}, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        st.session_state["spotify_access_token"] = data.get("access_token") or data.get("access_token")
        profile = data.get("profile", {}) or {}

        # If profile was passed in redirect (sp_avatar) it may be in query params — prefer that
        avatar_q = _q.get("sp_avatar", [None])[0] or ""
        if avatar_q:
            avatar_url = unquote(avatar_q)
            profile_images = profile.get("images") or []
            if not profile_images:
                profile["images"] = [{"url": avatar_url}]

        # Normalize alternative keys into Spotify-style images list
        if not profile.get("images"):
            alt = profile.get("avatar_url") or profile.get("avatar") or profile.get("picture")
            if alt:
                profile["images"] = [{"url": alt}]

        st.session_state["spotify_profile"] = profile
        st.session_state["sid"] = sid

        # clear query params so tokens/avatars aren't left in the URL
        st.experimental_set_query_params()
    except Exception as e:
        st.warning(f"Failed to hydrate Spotify session: {e}")




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

/* Welcome hero — centered, card-like */
.hero{ border:var(--border); background:linear-gradient(180deg,#141821dd,#0f1115cc); backdrop-filter:blur(8px);
       border-radius:var(--radius); padding:20px 24px; }
.hero h1{ margin:0 0 6px 0; font-size:clamp(1.4rem,2.2vw,2.1rem); letter-spacing:.3px; }
.hero p{ margin:0; color:var(--muted); }
.hero__left{ flex:1; }
.hero__title{ margin:0 0 8px 0; font-size:clamp(1.6rem,2.8vw,2.6rem); letter-spacing:.2px; font-weight:800; color:var(--text); }
.hero__lead{ margin:0; color:var(--muted); font-size:1.05rem; line-height:1.4; }
.hero__cta{ margin-top:16px; display:flex; gap:12px; align-items:center; }

/* Large primary CTA */
.cta-btn{
  background:var(--primary)!important; color:#000!important; padding:12px 20px; font-weight:800; border-radius:12px; border:none;
  box-shadow:0 10px 30px rgba(29,185,84,0.12); cursor:pointer; text-decoration:none;
}

.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"]>div, .stNumberInput input,
.stMultiSelect div[data-baseweb="select"]>div {
  background: rgba(255,255,255,.04)!important; color:var(--text)!important; border:var(--border)!important; border-radius:12px!important;
}

.cta-ghost{ background:transparent; color:var(--muted); border:1px solid rgba(255,255,255,0.06); padding:10px 16px; border-radius:12px; }

/* Right panel preview */
.hero__preview{ width:300px; min-width:220px; border-radius:12px; overflow:hidden; background:linear-gradient(180deg,#071217,#061014); padding:14px; border:var(--border); }
.hero__preview h4{ margin:0 0 8px 0; font-size:1rem; color:var(--text); }
.preview-track{ display:flex; gap:10px; align-items:center; margin-bottom:10px; }
.preview-track img{ width:48px; height:48px; border-radius:8px; object-fit:cover; }


/* Default buttons */
.stButton button{
  background:var(--primary)!important; color:#000000!important; font-weight:700!important; border-radius:12px!important;
  padding:10px 16px!important; border:none!important; transition:transform .08s ease, box-shadow .08s ease;
}
.stButton button:hover{ transform:translateY(-1px); box-shadow:0 8px 24px #1db95433; }
.stButton button:active{ transform:translateY(0) scale(.99); }

/* ONLY the Generate Playlist button in the sidebar */
section[data-testid="stSidebar"] div.stButton > button{
  color:#000000 !important;
  -webkit-text-fill-color:#000000 !important;
  text-shadow:none !important;
  font-weight:800 !important;
  font-size:16px !important;
  mix-blend-mode: normal !important;
}

.badges{ display:flex; flex-wrap:wrap; gap:.4rem; margin:.3rem 0 .2rem; }
.badge{ display:inline-flex; align-items:center; gap:.35rem; border:var(--border); color:var(--muted);
        padding:.30rem .55rem; border-radius:999px; font-size:.85rem; background:linear-gradient(180deg,#151924,#0f1115); }

/* Cards grid */
.grid{ display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:1.1rem; margin-top:.6rem; }
.card{ border:var(--border); background:var(--card); border-radius:16px; overflow:hidden; transition:transform .08s, box-shadow .08s; }
.card:hover{ transform:translateY(-2px); box-shadow:0 10px 30px rgba(0,0,0,.35); }
.card__body{ padding:12px 14px 14px; }
.card__title{ margin:.2rem 0 .55rem; font-size:15px; font-weight:700; letter-spacing:.2px; }
.track iframe{ width:100%; height:152px; border:0; }
.meta{ display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.55rem; }
.footer{ color:var(--muted); font-size:13px; text-align:center; padding:16px 0 6px; opacity:.9; }

/* profile pill */
.profile-pill { display:flex; align-items:center; gap:10px; font-weight:600; color:var(--text-color); }
.profile-pill img { width:40px; height:40px; border-radius:50%; object-fit:cover; }
.profile-pill .meta { display:flex; flex-direction:column; line-height:1; }
.profile-pill .meta .name { font-size:0.95rem; }
.profile-pill .meta .email { font-size:0.8rem; opacity:0.75; }

/* Shorter Connect button  */
      .connect-link {
        background: #1DB954;
        color: #fff;
        padding: 6px 12px;
        border-radius: 8px;
        text-decoration: none;
        font-weight:700;
        display:inline-block;
        min-width:110px;
        text-align:center;
      }
/* Responsive */
@media (max-width:900px){
  .hero{ flex-direction:column; padding:18px; gap:14px; }
  .hero__preview{ width:100%; min-width:auto; }
      }
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
if "spotify_access_token" not in st.session_state:
    st.session_state.spotify_access_token = None
if "spotify_profile" not in st.session_state:
    st.session_state.spotify_profile = None
if "bootstrapped" not in st.session_state:
    st.session_state.bootstrapped = True  # no server sync now



# -----------------------------
#  Browser helper: if user just came back from Spotify,
#    hydrate token/profile from backend cookie via /spotify/session/me
#    and drop them into the URL query (so Streamlit can read them).
# -----------------------------
components.html(f"""
<script>
(async () => {{
  // Helper: force Streamlit rerun by changing the real URL (not only history API)
  const navigate = (url) => {{
    try {{
      window.location.replace(url);   // causes a real navigation → Streamlit reruns
    }} catch (_) {{
      window.location.href = url;
    }}
  }};

  // 1) If we were just redirected back with ?sid=..., use it directly (cookie-less fallback)
  const url = new URL(window.location.href);
  const sid = url.searchParams.get("sid");

  if (sid) {{
    try {{
      const r = await fetch("{API_BASE}/spotify/session/by_sid?sid=" + encodeURIComponent(sid), {{
        credentials: "include",
        headers: {{ "Accept":"application/json" }}
      }});
      if (r.ok) {{
        const data = await r.json();
        const qp = new URLSearchParams(url.search);
        qp.delete("sid"); // scrub sid from URL once ingested
        if (data.access_token) {{
          qp.set("spotify_token", data.access_token);
        }}
        const prof = data.profile || {{}};
        if (prof.display_name) qp.set("sp_name", encodeURIComponent(prof.display_name));
        if (prof.email)        qp.set("sp_email", encodeURIComponent(prof.email));
        const avatar = (prof.images && prof.images[0] && prof.images[0].url) || "";
        if (avatar) qp.set("sp_avatar", encodeURIComponent(avatar));
        navigate(window.location.pathname + "?" + qp.toString());
        return; // done
      }}
    }} catch (e) {{
      console.warn("by_sid failed", e);
      // fall through to cookie flow
    }}
  }}

  // 2) Normal cookie-based flow: ask backend to read the sid cookie and hand us a fresh token
  try {{
    const resp = await fetch("{API_BASE}/spotify/session/me", {{
      credentials: "include",
      headers: {{ "Accept": "application/json" }}
    }});
    if (!resp.ok) return;

    const data = await resp.json();
    const token = data.access_token || "";
    const prof  = data.profile || {{}};
    if (!token) return;

    const qp = new URLSearchParams(window.location.search);
    qp.set("spotify_token", token);
    if (prof.display_name) qp.set("sp_name", encodeURIComponent(prof.display_name));
    if (prof.email)        qp.set("sp_email", encodeURIComponent(prof.email));
    const avatar = (prof.images && prof.images[0] && prof.images[0].url) || "";
    if (avatar) qp.set("sp_avatar", encodeURIComponent(avatar));

    // IMPORTANT: real navigation (not history.replaceState) so Streamlit reruns
    navigate(window.location.pathname + "?" + qp.toString());
  }} catch (e) {{
    console.warn("session/me failed", e);
  }}
}})();
</script>
""", height=0)



def _clear_qp(keys: List[str]):
    # Remove sensitive params from URL once ingested
    components.html(f"""
    <html><body>
    <script>
    const keys = {json.dumps(keys)};
    const qp = new URLSearchParams(window.location.search);
    let changed = false;
    keys.forEach(k => {{ if (qp.has(k)) {{ qp.delete(k); changed = true; }} }});
    if (changed) {{
        history.replaceState(null, '', window.location.pathname + (qp.toString() ? ('?' + qp.toString()) : ''));
    }}
    </script>
    </body></html>
    """, height=0)


# -----------------------------
# Ingest token/profile from URL → session_state, then scrub URL
# -----------------------------

qp = st.query_params
token = qp.get("spotify_token")
if isinstance(token, str) and token:
    st.session_state.spotify_access_token = token
    st.session_state.spotify_profile = {
        "display_name": qp.get("sp_name") or "",
        "email": qp.get("sp_email") or "",
        "avatar_url": qp.get("sp_avatar") or "",
    }
    components.html("""
    <script>
      const qp = new URLSearchParams(window.location.search);
      ["spotify_token","sp_name","sp_email","sp_avatar","sid","fetch_session"].forEach(k => qp.delete(k));
      history.replaceState(null, "", window.location.pathname + (qp.toString()?("?"+qp.toString()):""));
    </script>
    """, height=0)

# -----------------------------
# LOGIN PANE (early return gate)
#    If no token yet, show a tiny login panel and stop rendering.
# -----------------------------
if not st.session_state.get("spotify_access_token"):
    
    login_url = f"{API_BASE}/spotify/login"
     # Friendly landing hero for the login/guest choice
    st.markdown(
            f"""
<div style="max-width:980px;margin:28px auto;padding:28px;border-radius:18px;
            background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
            box-shadow:0 18px 40px rgba(0,0,0,0.6); display:flex; gap:20px; align-items:center;">
  <div style="flex:1;">
    <h2 style="margin:0 0 8px;color:#ecf1f8;font-size:1.6rem;">Welcome to Music Recommendation AI</h2>
    <p style="margin:0 0 14px;color:#9aa4b2;font-size:1rem;line-height:1.4;">
      Tell us your vibe and we'll craft a playlist for the moment. Connect Spotify for the best experience —
      or continue as a guest with local saves and limited recommendations.
    </p>
    <div style="display:flex;gap:12px;align-items:center;">
      <a href="{login_url}" style="background:#1DB954;color:#000;padding:12px 18px;border-radius:12px;font-weight:800;
         text-decoration:none;display:inline-block;">🎧 Connect Spotify</a>
      <button id="guest_continue" style="background:transparent;border:1px solid rgba(255,255,255,0.06);
         color:#9aa4b2;padding:10px 14px;border-radius:10px;font-weight:700;">Continue without Spotify</button>
    </div>
    <p style="margin-top:12px;color:#7f8b95;font-size:.92rem;">Tip: connecting enables saved playlists to be associated with your account and richer personalized picks.</p>
  </div>
  <div style="width:220px;min-width:160px;">
    <img alt="music illustration" src="https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?q=80&w=800&auto=format&fit=crop&s=1a8b7f2f6e4a5d1a2b3c4d5e6f7g8h9i"
         style="width:100%;border-radius:12px;object-fit:cover;display:block;" />
  </div>
</div>
""",
            unsafe_allow_html=True,
    )
    st.stop()

# -----------------------------
# OAuth helpers (browser ↔ backend)
# -----------------------------
# def _inject_fetch_session():
#     components.html(f"""
# <html><body>
# <script>
# (async () => {{
#   try {{
#     const resp = await fetch('{API_BASE}/spotify/session/me', {{
#       credentials: 'include',
#       headers: {{ 'Accept':'application/json' }}
#     }});
#     if (!resp.ok) {{
#       // if unauthorized, clear any stale params and leave (sidebar will show Connect)
#       const qp = new URLSearchParams(window.location.search);
#       ["spotify_token","sp_name","sp_email","sp_avatar"].forEach(k => qp.delete(k));
#       history.replaceState(null, '', window.location.pathname + (qp.toString() ? ('?' + qp.toString()) : ''));
#       return;
#     }}
#     const data = await resp.json();

#     const token = data.access_token || '';
#     const prof  = data.profile || {{}};
#     const name  = encodeURIComponent(prof.display_name || '');
#     const email = encodeURIComponent(prof.email || '');
#     const avatar= encodeURIComponent((prof.images && prof.images[0] && prof.images[0].url) || '');

#     const qp = new URLSearchParams(window.location.search);
#     if (token) qp.set('spotify_token', token);
#     if (name)  qp.set('sp_name', name);
#     if (email) qp.set('sp_email', email);
#     if (avatar)qp.set('sp_avatar', avatar);

#     history.replaceState(null, '', window.location.pathname + (qp.toString() ? ('?' + qp.toString()) : ''));
#   }} catch (e) {{
#     console.error('session/me failed', e);
#   }}
# }})();
# </script>
# </body></html>
# """, height=0)
    
# _inject_fetch_session()


# def _session_watchdog():
#     components.html(f"""
# <html><body><script>
# (async () => {{
#   try {{
#     const resp = await fetch('{API_BASE}/spotify/session/me', {{
#       credentials: 'include',
#       headers: {{ 'Accept':'application/json' }}
#     }});
#     if (resp.status === 401) {{
#       window.location.replace('{FRONTEND_URL}/00_landing');
#     }}
#   }} catch (e) {{}}
# }})();
# </script></body></html>
# """, height=0)


# _session_watchdog()





# -----------------------------
# Sidebar (TOP: profile card • then controls)
# -----------------------------
with st.sidebar:
    prof = st.session_state.spotify_profile
    token = st.session_state.spotify_access_token

# profile pill
    _profile = st.session_state.get("spotify_profile") or {}
    _sp_name = ""
    _sp_email = ""
    _sp_img = ""

    if isinstance(_profile, dict):
        _sp_name = _profile.get("display_name") or _profile.get("name") or ""
        _sp_email = _profile.get("email") or _profile.get("sp_email") or ""
        # Spotify "images" is a list of dicts like [{"url": "..."}]
        imgs = _profile.get("images") or []
        if isinstance(imgs, list) and len(imgs) > 0 and isinstance(imgs[0], dict):
            _sp_img = imgs[0].get("url") or ""
        # fallback fields if your app stored a profile image under a different key:
        _sp_img = _sp_img or _profile.get("avatar_url") or _profile.get("profile_img") or _profile.get("avatar") or _profile.get("picture") or ""

    # Render: if logged-in show profile pill; otherwise show a compact Connect button
    if _sp_name or _sp_img:
    # only include the <img> tag when we actually have an image URL;
    # use inline styles to guarantee size + object-fit even if CSS class isn't applied.
        img_html = (
            f'<img src="{_sp_img}" alt="profile image" '
            f'style="width:40px;height:40px;border-radius:50%;object-fit:cover;display:block;"/>'
            if _sp_img else ""
        )
        st.markdown(
            f"""
            <div class="profile-pill" role="group" aria-label="user profile">
            {img_html}
            <div class="meta">
                <div class="name">{_sp_name or 'Spotify user'}</div>
                <div class="email">{_sp_email or ''}</div>
            </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # shorter connect button (anchor -> opens FastAPI /spotify/login)
        login_url = f"{API_BASE}/spotify/login"
        st.markdown(f'<a class="connect-link" href="{login_url}">Connect Spotify</a>', unsafe_allow_html=True)



    st.markdown("---")

    
    cols_lr = st.columns([1,1])
    col_logout = cols_lr[0]
    col_refresh = cols_lr[1]
    with col_logout:
        if st.button("Log out"):
            components.html(f"""
        <script>
        (async () => {{
          try {{
            await fetch("{API_BASE}/spotify/logout", {{
              method: "POST",
              credentials: "include",
              headers: {{ "Accept":"application/json" }}
            }});
          }} catch (e) {{
            console.warn("Logout request failed", e);
          }}
          // Ensure we remove sensitive query params and force a real navigation
          const qp = new URLSearchParams(window.location.search);
          ["spotify_token","sp_name","sp_email","sp_avatar","sid","fetch_session"].forEach(k => qp.delete(k));
          // small delay to allow server to clear cookie
          setTimeout(() => {{
            window.location.replace(window.location.pathname + (qp.toString()?("?"+qp.toString()):""));
          }}, 250);
        }})();
        </script>
        """, height=0)
            # Clear client-side session state immediately as a best-effort
            st.session_state.spotify_access_token = None
            st.session_state.spotify_profile = None
            st.stop()
    with col_refresh:
        if st.button("Refresh token"):
            components.html("""
            <script>
              // force the session-me hydrator to run again on next rerun
              const qp = new URLSearchParams(window.location.search);
              qp.set("fetch_session", "1");
              location.replace(window.location.pathname + "?" + qp.toString());
            </script>
            """, height=0)
            st.stop()

    st.divider()
    st.subheader("Playlist Settings")

    # --- Vibe text ---
    vibe_description = st.text_area(
        "Describe your vibe",
        value=st.session_state.get("vibe_prefill", ""),
        placeholder='e.g., "rainy bus ride, calm focus, minimal vocals"',
        height=110,
    )

    # --- Read fused mood from session or query (?mood=) (kept behavior)
    def _read_fused_mood_label() -> Optional[str]:
        lbl = st.session_state.get("fused_mood_label")
        if isinstance(lbl, str) and lbl.strip():
            return lbl.strip()
        val = st.query_params.get("mood", None)
        s = (val or "").strip() if isinstance(val, str) else None
        return s or None

    fused_label = _read_fused_mood_label()
    fused_conf  = st.session_state.get("fused_mood_conf")

    # --- Mood source + value ---
    mood_options = ["happy","sad","energetic","chill","focus","romantic","angry","calm"]
    use_quiz = st.radio(
        "Use mood from",
        ["Quiz (recommended)", "Manual"],
        index=0 if fused_label else 1,
        horizontal=True,
        key="mood_source_radio",
    )

    if use_quiz == "Quiz (recommended)":
        effective_mood = fused_label or "chill"
        if fused_label:
            st.caption(f'From quiz: **{fused_label}**' + (f" (conf {fused_conf})" if fused_conf is not None else ""))
        if st.button("🧩 Take / retake quiz"):
            st.switch_page("pages/mood_ui.py")
        st.page_link("pages/mood_ui.py", label="Open mood quiz page")
    else:
        manual_index = mood_options.index(fused_label) if fused_label in mood_options else 3
        manual_mood = st.selectbox("Select mood", mood_options, index=manual_index, key="manual_mood_select")
        effective_mood = manual_mood

    st.session_state["effective_mood"] = effective_mood

    activity = st.selectbox(
        "Activity",
        ["workout", "study", "party", "relax", "commute", "sleep", "none"],
        index=1,
    )
    genre_or_language = st.text_input("Genre", placeholder="hip hop, r&b, lofi")
    prefer_auto = st.toggle("Prefer auto-detected genre if available", value=True)
    exclude_explicit = st.toggle("Exclude explicit lyrics", value=False)
    limit = st.slider("Tracks per playlist", 5, 20, 12)

    with st.expander("Advanced"):
        show_debug = st.checkbox("Show analyzer debug", value=False)

    go = st.button("Generate Playlist", use_container_width=True, key="btn_generate")

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
# Helpers
# -----------------------------
def call_analyzer(text: str) -> Optional[dict]:
    if not (text or "").strip():
        return None
    try:
        r = requests.post(f"{API_BASE}/analyze", json={"text": text}, headers=_h(), timeout=10)
        return r.json() if r.ok else None
    except Exception:
        return None

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
# Tabs
# -----------------------------
tab_build, tab_saved, tab_about, tab_for_you = st.tabs(["Builder", "Saved", "How it works","For You"])

# =============================
# Builder
# =============================
with tab_build:
    if go:
        if not (vibe_description or "").strip():
            st.warning("Please enter a short vibe description.")
            st.stop()

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
            s.write("Step 1 • Analyzing your preferences (mood/genre hints)")
            analysis = call_analyzer(str(vibe_description or ""))
            auto_mood = (analysis or {}).get("mood")
            auto_genre = (analysis or {}).get("genre")

            selected = st.session_state.get("effective_mood")
            mood_final = None if (not selected or selected == "Auto-detect") else selected
            if mood_final is None:
                mood_final = auto_mood or st.session_state.get("fused_mood_label") or "chill"

            genre_final = (genre_or_language or "").strip()
            if prefer_auto and not genre_final:
                genre_final = (auto_genre or "").strip()

            if st.session_state.get("show_debug", False) or True:  # keep same switch behavior
                if show_debug:
                    st.code(json.dumps({"analysis": analysis, "mood_final": mood_final, "genre_final": genre_final}, indent=2), language="json")

            s.update(label="Crafting your playlist • Retrieving candidates and scoring")
            s.write("Step 2 • Pulling tracks from Spotify and ranking for relevance")
            try:
                st.session_state.used_track_ids = {str(x) for x in (st.session_state.used_track_ids or set()) if x}
                playlist_items, st.session_state.used_track_ids = generate_playlist_from_user_settings(
                    vibe_description=str(vibe_description or ""),
                    mood=mood_final,
                    activity=("" if activity == "none" else activity),
                    genre_or_language=genre_final,
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

            st.session_state.gen_data = {
                "items": playlist_items,
                "desc": desc,
                "mood_final": mood_final,
                "activity_final": (activity if activity != "none" else None),
                "genre_final": (genre_final or None),
                "vibe_description": vibe_description,
                "exclude_explicit": exclude_explicit,
                "limit": limit,
            }

            try:
                s.update(label="Playlist ready", state="complete", expanded=False)
            except Exception:
                pass

        st.toast("Playlist generated.")

    gd = st.session_state.get("gen_data")
    empty_hint = st.empty()

    if gd:
        empty_hint.empty()
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
        moods: List[str] = sorted({
            str(m).strip()
            for m in (r.get("mood") for r in rows)
            if m is not None and str(m).strip() != ""
        })
        activities: List[str] = sorted({
            str(a).strip()
            for a in (r.get("activity") for r in rows)
            if a is not None and str(a).strip() != ""
        })

        fc1, fc2, fc3 = st.columns(3)
        f_mood = fc1.selectbox("Filter mood", ["All"] + moods, index=0)
        f_activity = fc2.selectbox("Filter activity", ["All"] + activities, index=0)
        f_genre = fc3.text_input("Filter genre contains", value="")

        from typing import Callable
        def _keep(r: Dict[str, Any]) -> bool:
            if f_mood != "All" and r.get("mood") != f_mood:
                return False
            if f_activity != "All" and r.get("activity") != f_activity:
                return False
            if f_genre and f_genre.lower() not in (r.get("genre_or_language") or "").lower():
                return False
            return True

        _keep_fn: Callable[[Dict[str, Any]], bool] = _keep
        view = [r for r in rows if _keep_fn(r)] #type: ignore

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
- Sign in with a simple local account (stored securely in `.appdata/users.json`).
- Analyze your vibe via an NLP agent (`/analyze`) to infer mood and genre (optional).
- Combine your choices with auto-detected suggestions.
- Fetch & score tracks via `app.spotify.generate_playlist_from_user_settings(...)`.
- Explain the playlist using `generate_playlist_description(...)` (optional).
- Embed tracks and save to `.appdata/saved_playlists.json`. Open/Delete from the Saved tab.
"""
    )



# =============================
# For You (NEW TAB)
# =============================
with tab_for_you:
    st.subheader("For You • personalized picks")

    token = st.session_state.get("spotify_access_token")

    def _profile_from_saved(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        from collections import Counter
        artists = Counter()
        genres = Counter()
        tracks = Counter()
        for r in rows:
            for t in (r.get("tracks") or []):
                for a in (t.get("artists") or []):
                    artists[a] += 1
                for g in (t.get("genres") or []):
                    genres[str(g).lower()] += 1
                if t.get("id"): tracks[t["id"]] += 1
        return {
            "top_artists": [a for a,_ in artists.most_common(5)],
            "top_genres": [g for g,_ in genres.most_common(5)],
            "top_tracks": [t for t,_ in tracks.most_common(5)],
        }

    cols = st.columns([1,1,1,1])
    limit_for_you = cols[0].slider("How many", 8, 50, 24, 1, key="for_you_limit")
    refresh_for_you = cols[1].button("Refresh", key="for_you_refresh")

    if refresh_for_you or "for_you_cache" not in st.session_state:
        if token:
            try:
                r = requests.get(
                    f"{API_BASE}/spotify/for_you",
                    headers={"x-api-key": API_KEY, "Authorization": f"Bearer {token}"},
                    params={"limit": limit_for_you},
                    timeout=25,
                )
                r.raise_for_status()
                st.session_state["for_you_cache"] = r.json()
            except Exception as e:
                st.session_state["for_you_cache"] = {"error": str(e)}
        else:
            st.session_state["for_you_cache"] = {"note": "no_token"}

    cache = st.session_state.get("for_you_cache", {})

    if cache.get("error"):
        st.error(f"Could not fetch recommendations: {cache['error']}")

    if cache.get("recommendations"):
        prof = cache.get("profile", {})
        recs = cache.get("recommendations", [])

        st.caption("Profile seeds learned from your saved playlists:")
        st.write(
            " • ".join([
                f"Artists: {', '.join(prof.get('top_artist_ids', [])[:3]) or '—'}",
                f"Genres: {', '.join(prof.get('top_genres', [])[:3]) or '—'}",
                f"Tracks: {', '.join(prof.get('top_track_ids', [])[:3]) or '—'}",
            ])
        )

        st.markdown('<div class="grid">', unsafe_allow_html=True)
        for tr in recs[:limit_for_you]:
            tid = tr.get("id")
            if not tid:
                continue
            artists = ", ".join(tr.get("artists", []))
            title = f"{tr.get('name','Unknown')} — {artists}"
            embed = f"https://open.spotify.com/embed/track/{tid}?utm_source=generator"
            st.markdown(
                f"""
<div class="card">
  <div class="track"><iframe src="{embed}" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe></div>
  <div class="card__body">
    <div class="card__title">{title}</div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    elif cache.get("note") == "no_token":
        rows = list_playlists()
        if not rows:
            st.info("No saved playlists yet. Save a few to unlock personalized recommendations.")
        else:
            prof = _profile_from_saved(rows)
            st.caption("Learned from your saved playlists (local):")
            st.write(
                " • ".join([
                    f"Top artists: {', '.join(prof['top_artists']) or '—'}",
                    f"Top genres: {', '.join(prof['top_genres']) or '—'}",
                ])
            )
            st.info("Connect Spotify in your backend to enable similar-track discovery. Showing some resurfaced favorites.")
            shown = set()
            st.markdown('<div class="grid">', unsafe_allow_html=True)
            for r in rows:
                for t in r.get("tracks", []):
                    tid = t.get("id")
                    if not tid or tid in shown:
                        continue
                    shown.add(tid)
                    artists = ", ".join(t.get("artists", []))
                    title = f"{t.get('name','Unknown')} — {artists}"
                    embed = f"https://open.spotify.com/embed/track/{tid}?utm_source=generator"
                    st.markdown(
                        f"""
<div class="card">
  <div class="track"><iframe src="{embed}" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe></div>
  <div class="card__body">
    <div class="card__title">{title}</div>
  </div>
</div>
""",
                        unsafe_allow_html=True,
                    )
                    if len(shown) >= limit_for_you:
                        break
                if len(shown) >= limit_for_you:
                    break
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Click Refresh to fetch your personalized picks.")


# -----------------------------
# Footer
# -----------------------------
st.markdown("<div class='footer'>Built for your Agentic Music Recommender • Modern UI + Save/Load</div>", unsafe_allow_html=True)
