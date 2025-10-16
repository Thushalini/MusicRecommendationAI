# 🎵 Music Recommendation AI

This is our group project **Music Recommendation AI**.  
It generates personalized Spotify playlists based on **mood, genre, and context**, and integrates with other agents such as Mood Detector and Genre Classifier.

---

## 🚀 Features
- Modern **Streamlit UI** for playlist creation  
- **FastAPI backend** for handling requests  
- Spotify API integration (search, recommendations)  
- Explainable recommendations (reasons why each track is suggested)  
- Playlist persistence: save, load, and delete playlists  
- Supports **mood** (happy, sad, energetic, chill, etc.) and **context** (workout, study, party, relax, etc.)

---

## ⚙️ Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/playList-Builder.git
   cd playList-Builder
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/Mac
   venv\Scripts\activate      # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 🔑 Environment Setup

Create a **`.env`** file in the project root:

```env
# Spotify API
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/callback
SPOTIFY_MARKET=IN

# API
AGENTS_API_BASE=http://127.0.0.1:8000
AGENTS_API_KEY=dev-key-change-me

OPENAI_API_KEY=your_openapi_key
```

---

## ▶️ Running the Project

**FastAPI backend** 
```bash
uvicorn app.fastapi_agents:app --host 127.0.0.1 --port 8000 --reload
```

Start the **Streamlit UI**:
```bash
streamlit run main.py
```

Now open [http://localhost:8501](http://localhost:8000) in your browser.

---

## 🧪 Example Request (FastAPI)
```bash
curl -X POST http://127.0.0.1:8000/playList_Builder \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev-key-change-me" \
  -d '{
        "mood": "chill",
        "genre": "lofi",
        "context": "study",
        "limit": 15
      }'
```

---

## 📌 Requirements
- Python 3.10+
- Spotify Developer account + API credentials
- Internet connection for Spotify API

---

## 👥 Team Roles
- **Playlist Builder Agent** – This repo  
- **Mood Detector Agent** – detects mood from text input  
- **Genre Classifier Agent** – classifies music genres  
- **User Preference Manager Agent** – tracks history & preferences  

---

## 📜 License
This project is for **academic purpose** (IT3041 – IRWA Group Project).  
