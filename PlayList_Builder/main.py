import streamlit as st
st.set_page_config(page_title="Music Rec AI", page_icon="🎧", layout="wide")
st.title("Welcome 👋 to Music Recommendation AI")
st.page_link("pages/mood_ui.py", label="Quiz", icon="❓")
st.page_link("pages/streamlit_app.py", label="Playlist", icon="🎵")

st.markdown("""
<style>
/* Hide the default page selector sidebar */
section[data-testid="stSidebar"] {display: none !important;}
/* Expand main content to full width */
div.block-container {padding-left: 2rem; padding-right: 2rem;}
</style>
""", unsafe_allow_html=True)

