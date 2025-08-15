# MusicRecommendationAI
Agentic AI-Based System for Music Recommendation


1. Mood Detector Agent 🎭

Role: Analyzes audio features (tempo, pitch, rhythm, timbre) and/or user input (facial expressions, text, physiological signals) to detect the listener's mood (e.g., happy, sad, energetic, calm).

Core Tech:

Audio analysis models (e.g., librosa for feature extraction + emotion classification ML model).

NLP sentiment analysis for text-based mood input.

Optional: Computer vision for face emotion recognition.

2. Genre Classification Agent 🎼

Role: Classifies each song into one or more genres using machine learning on audio features and metadata.

Core Tech:

CNN/RNN models for audio spectrogram classification.

Metadata parsing from song tags (artist, album, etc.).

Integration with external APIs (Spotify, Last.fm) for additional genre data.

3. Playlist Builder Agent 📜

Role: Generates personalized playlists based on detected mood, preferred genres, and listening history.

Core Tech:

Recommendation algorithms (Collaborative Filtering, Content-Based Filtering, Hybrid models).

Rules for balancing mood alignment, tempo, and variety.

Dynamic playlist updates when mood changes.

4. User Profile & Preference Manager Agent 👤

Role: Maintains and updates a dynamic profile for each user, storing:

Listening history.

Preferred genres/artists.

Typical mood patterns (time of day, day of week).

Core Tech:

Database for user preferences & history.

Adaptive learning to refine recommendations over time.
