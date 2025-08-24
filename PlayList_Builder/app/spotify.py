# app/spotify.py
import os
import re
import random
import base64
import unicodedata
import requests
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional

# scoring utilities
from app.scoring import mood_targets, score_tracks, reason_string

# ----------------------------
# Env
# ----------------------------
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID") or os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET") or os.getenv("SPOTIFY_CLIENT_SECRET")
DEFAULT_MARKET = os.getenv("SPOTIFY_MARKET", "IN")

# NEW: prioritized list of markets to try (comma-separated)
MARKETS_PREF = [
    m.strip().upper()
    for m in (os.getenv("SPOTIFY_MARKETS", "") or "").split(",")
    if m.strip()
]

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("Spotify API credentials not set. Please check your .env file.")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # not used here directly

# ----------------------------
# Resilient HTTP session
# ----------------------------
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=50)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

SESSION = _build_session()

# ----------------------------
# Token Handling
# ----------------------------
def get_spotify_token() -> str:
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {b64_auth_str}"}
    data = {"grant_type": "client_credentials"}
    r = SESSION.post("https://accounts.spotify.com/api/token", headers=headers, data=data, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]

SPOTIFY_TOKEN = get_spotify_token()
HEADERS = {"Authorization": f"Bearer {SPOTIFY_TOKEN}"}

def refresh_token_if_needed(resp: requests.Response) -> bool:
    global SPOTIFY_TOKEN, HEADERS
    if resp is not None and resp.status_code == 401:
        SPOTIFY_TOKEN = get_spotify_token()
        HEADERS = {"Authorization": f"Bearer {SPOTIFY_TOKEN}"}
        return True
    return False

def sp_get(url: str, params: dict | None = None) -> dict | None:
    try:
        r = SESSION.get(url, headers=HEADERS, params=params, timeout=12)
        if refresh_token_if_needed(r):
            r = SESSION.get(url, headers=HEADERS, params=params, timeout=12)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        url_dbg = getattr(r, "url", url)
        print(f"HTTP Error: {getattr(e, 'response', None) and getattr(e.response,'status_code',None)} | {e} | URL: {url_dbg}")
        return None

# ----------------------------
# Helpers
# ----------------------------
def _rand_offset(max_offset: int = 500) -> int:
    """Random offset for Spotify pagination to vary results each build."""
    return random.randint(0, max_offset)

def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").strip().lower()

def tokenize(text: str) -> List[str]:
    if not text:
        return []
    phrases = re.findall(r'"([^"]+)"', text)
    remainder = re.sub(r'"[^"]+"', ' ', text or '')
    words = re.findall(r"[A-Za-z0-9\-']+", remainder)
    toks = [p.strip() for p in phrases if p.strip()] + [w.strip() for w in words if w.strip()]
    out, seen = [], set()
    for t in toks:
        tn = _norm(t)
        if tn and tn not in seen:
            out.append(tn)
            seen.add(tn)
    return out

# ----------------------------
# Language & Genre parsing
# ----------------------------
LANG_ALIASES = {
    # existing
    "sinhala": {"si", "sinhala", "sinhalese"},
    "tamil": {"ta", "tamil"},
    "hindi": {"hi", "hindi"},
    "english": {"en", "english"},
    # NEW languages (tokens that should be treated as language, not genre)
    "korean": {"ko", "korean", "hangul"},
    "japanese": {"ja", "japanese", "nihongo"},
    "spanish": {"es", "spanish", "español"},
    "portuguese": {"pt", "portuguese", "português", "brasileiro", "brazilian"},
    "french": {"fr", "french", "français"},
    "german": {"de", "german", "deutsch"},
    "arabic": {"ar", "arabic", "عربي", "arab"},
    "turkish": {"tr", "turkish", "türkçe"},
    "russian": {"ru", "russian", "русский"},
    "indonesian": {"id", "indonesian", "bahasa"},
    "thai": {"th", "thai"},
    "chinese": {"zh", "chinese", "mandarin", "cantonese", "zh-hans", "zh-hant"},
}

def _is_range(text: str, ranges: List[Tuple[int,int]]) -> bool:
    return any(lo <= ord(c) <= hi for c in text for (lo, hi) in ranges)

def _is_sinhala(text: str) -> bool:
    return _is_range(text, [(0x0D80, 0x0DFF)])

def _is_tamil(text: str) -> bool:
    return _is_range(text, [(0x0B80, 0x0BFF)])

def _is_devanagari(text: str) -> bool:  # Hindi
    return _is_range(text, [(0x0900, 0x097F)])

# NEW script checks
def _is_hangul(text: str) -> bool:      # Korean
    return _is_range(text, [(0x1100,0x11FF),(0x3130,0x318F),(0xAC00,0xD7AF)])

def _is_hiragana(text: str) -> bool:    # Japanese
    return _is_range(text, [(0x3040,0x309F)])

def _is_katakana(text: str) -> bool:    # Japanese
    return _is_range(text, [(0x30A0,0x30FF)])

def _is_cjk(text: str) -> bool:         # CJK ideographs (Chinese & also used in JP)
    return _is_range(text, [(0x4E00,0x9FFF)])

def _is_arabic_script(text: str) -> bool:
    return _is_range(text, [(0x0600,0x06FF),(0x0750,0x077F)])

def _is_thai_script(text: str) -> bool:
    return _is_range(text, [(0x0E00,0x0E7F)])

def _is_cyrillic(text: str) -> bool:
    return _is_range(text, [(0x0400,0x04FF)])

def _detect_lang_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    if _is_sinhala(text): return "sinhala"
    if _is_tamil(text): return "tamil"
    if _is_devanagari(text): return "hindi"
    if _is_hangul(text): return "korean"
    if _is_hiragana(text) or _is_katakana(text): return "japanese"
    if _is_arabic_script(text): return "arabic"
    if _is_thai_script(text): return "thai"
    if _is_cyrillic(text): return "russian"
    # CJK without kana → treat as Chinese (likely)
    if _is_cjk(text): return "chinese"
    return None  # likely english/latin

def parse_language_and_genres(genre_or_language: Optional[str]) -> Tuple[Optional[str], List[str]]:
    """
    Returns (language, genres[]) with multi-word fixes (e.g., "hip hop", "r&b", "lofi").
    Accepts tokens like: si/ta/hi/en, sinhala/tamil/hindi/english, and language names above.
    Everything else is treated as a genre term.
    """
    if not genre_or_language:
        return None, []

    raw = genre_or_language.strip()

    # 1) Quoted phrases as single tokens
    phrases = re.findall(r'"([^"]+)"', raw)
    remainder = re.sub(r'"[^"]+"', ' ', raw)

    # 2) Split remainder by , | / and then by spaces
    chunks = re.split(r"[,\|/]+", remainder)

    tokens: List[str] = []
    for c in chunks:
        c = _norm(c)
        if c:
            tokens.extend(c.split())

    # Add back phrases (normalized)
    tokens.extend([_norm(p) for p in phrases if p.strip()])

    # 3) Stitch common multi-word genres
    fixed: List[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        nxt = tokens[i+1] if i+1 < len(tokens) else ""
        nxt2 = tokens[i+2] if i+2 < len(tokens) else ""

        if t == "hip" and nxt == "hop":
            fixed.append("hip hop"); i += 2; continue
        if t == "r" and nxt == "and" and nxt2 == "b":
            fixed.append("r&b"); i += 3; continue
        if t == "lo" and nxt == "fi":
            fixed.append("lofi"); i += 2; continue

        fixed.append(t); i += 1

    # 4) Separate language aliases vs genres
    lang: Optional[str] = None
    genres: List[str] = []
    for tok in fixed:
        matched_lang = None
        for L, aliases in LANG_ALIASES.items():
            if tok in aliases:
                matched_lang = L
                break
        if matched_lang:
            lang = matched_lang
        else:
            genres.append(tok)

    genres = list(dict.fromkeys(genres))  # de-dup, preserve order
    return lang, genres

GENRE_ALIASES = {
    "lofi": {"lofi", "lo-fi", "lo_fi", "lowfi"},
    "hip hop": {"hip hop", "hip-hop", "rap"},
    "r&b": {"r&b", "rnb", "r and b"},
    "edm": {"edm", "electronic", "dance"},
    "k-pop": {"k-pop", "kpop"},
    "j-pop": {"j-pop", "jpop"},
    "pop": {"pop"},
    "rock": {"rock", "alt rock", "alternative"},
    "indie": {"indie", "indie pop", "indie rock"},
    "classical": {"classical", "orchestral"},
    "jazz": {"jazz"},
    "sinhala": {"sinhala"},
    "tamil": {"tamil"},
    "hindi": {"hindi"},
    "english": {"english"},
}

def _genre_match_token_set(g: str) -> Set[str]:
    g = _norm(g)
    for canon, aliases in GENRE_ALIASES.items():
        if g == canon or g in aliases:
            return {canon, *aliases}
    return {g}

# ----------------------------
# Artist genres (BATCH + CACHE)
# ----------------------------
ARTIST_GENRE_CACHE: Dict[str, List[str]] = {}

def _ensure_artist_genres_cached(artist_ids: List[str]) -> None:
    missing = [a for a in artist_ids if a and a not in ARTIST_GENRE_CACHE]
    if not missing:
        return
    for i in range(0, len(missing), 50):
        chunk = missing[i:i+50]
        data = sp_get("https://api.spotify.com/v1/artists", params={"ids": ",".join(chunk)})
        if not data or "artists" not in data:
            continue
        for a in (data.get("artists") or []):
            if not a or not isinstance(a, dict):
                continue
            aid = a.get("id")
            if not aid:
                continue
            ARTIST_GENRE_CACHE[aid] = [_norm(g) for g in (a.get("genres", []) or [])]

def _artist_matches_genre_strict(artist_ids: List[str], genre_tokens: List[str]) -> bool:
    if not genre_tokens:
        return True
    _ensure_artist_genres_cached(artist_ids)
    expanded: List[Set[str]] = [_genre_match_token_set(g) for g in genre_tokens]
    artist_genres = set()
    for aid in artist_ids:
        for g in ARTIST_GENRE_CACHE.get(aid, []):
            artist_genres.add(_norm(g))
    for wanted in expanded:
        for w in wanted:
            for ag in artist_genres:
                if w in ag or ag in w:
                    return True
    return False

def _text_contains_any(text: str, tokens: List[str]) -> bool:
    tn = _norm(text)
    return any(t in tn for t in tokens if t)

def _track_matches_language(track: dict, desired_lang: Optional[str]) -> bool:
    if not desired_lang:
        return True
    name = track.get("name") or ""
    if desired_lang == "sinhala" and _is_sinhala(name): return True
    if desired_lang == "tamil"   and _is_tamil(name): return True
    if desired_lang == "hindi"   and _is_devanagari(name): return True
    if desired_lang == "korean"  and _is_hangul(name): return True
    if desired_lang == "japanese" and (_is_hiragana(name) or _is_katakana(name) or _is_cjk(name)): return True
    if desired_lang == "arabic"  and _is_arabic_script(name): return True
    if desired_lang == "thai"    and _is_thai_script(name): return True
    if desired_lang == "russian" and _is_cyrillic(name): return True
    if desired_lang == "chinese" and _is_cjk(name): return True

    for a in (track.get("artists") or []):
        an = a.get("name", "")
        if desired_lang == "sinhala" and _is_sinhala(an): return True
        if desired_lang == "tamil"   and _is_tamil(an): return True
        if desired_lang == "hindi"   and _is_devanagari(an): return True
        if desired_lang == "korean"  and _is_hangul(an): return True
        if desired_lang == "japanese" and (_is_hiragana(an) or _is_katakana(an) or _is_cjk(an)): return True
        if desired_lang == "arabic"  and _is_arabic_script(an): return True
        if desired_lang == "thai"    and _is_thai_script(an): return True
        if desired_lang == "russian" and _is_cyrillic(an): return True
        if desired_lang == "chinese" and _is_cjk(an): return True

    album = track.get("album", {}) or {}
    album_name = album.get("name", "")
    if desired_lang == "sinhala" and _is_sinhala(album_name): return True
    if desired_lang == "tamil"   and _is_tamil(album_name): return True
    if desired_lang == "hindi"   and _is_devanagari(album_name): return True
    if desired_lang == "korean"  and _is_hangul(album_name): return True
    if desired_lang == "japanese" and (_is_hiragana(album_name) or _is_katakana(album_name) or _is_cjk(album_name)): return True
    if desired_lang == "arabic"  and _is_arabic_script(album_name): return True
    if desired_lang == "thai"    and _is_thai_script(album_name): return True
    if desired_lang == "russian" and _is_cyrillic(album_name): return True
    if desired_lang == "chinese" and _is_cjk(album_name): return True

    if desired_lang == "english":
        return True
    return False

# ----------------------------
# Query variants (randomized)
# ----------------------------
def build_query_variants(vibe_description: str, mood: str | None = None,
                         activity: str | None = None, genre_or_language: str | None = None) -> List[str]:
    vd_tokens = tokenize(vibe_description)
    combos: List[str] = []
    if len(vd_tokens) >= 2:
        combos.append(" ".join(vd_tokens[:2]))
    if vd_tokens:
        combos.append(vd_tokens[0])
    for t in [mood, activity, genre_or_language]:
        if t and _norm(t) != "none":
            combos.append(t)
    seen: Set[str] = set()
    variants: List[str] = []
    for q in combos:
        qn = _norm(q)
        if qn and qn not in seen:
            variants.append(q)
            seen.add(qn)
    if vibe_description and _norm(vibe_description) not in seen:
        variants.append(vibe_description)
    random.shuffle(variants)
    return variants

# ----------------------------
# Search helpers (multi-offset, strict)
# ----------------------------
def search_tracks(query: str, limit: int, used_ids: Set[str],
                  required_lang: Optional[str], required_genres: List[str],
                  market: Optional[str], tries: int = 3) -> Tuple[List[dict], Set[str]]:
    tracks: List[dict] = []
    for _ in range(max(1, tries)):
        params = {"q": query, "type": "track", "limit": min(limit, 50)}
        if market:
            params["market"] = market
        params["offset"] = _rand_offset(450)

        data = sp_get("https://api.spotify.com/v1/search", params=params)
        if not data or "tracks" not in data:
            continue

        items = data.get("tracks", {}).get("items", []) or []
        if not items:
            continue

        all_artist_ids: List[str] = []
        for item in items:
            if not item or not isinstance(item, dict):
                continue
            for a in (item.get("artists") or []):
                if a and a.get("id"):
                    all_artist_ids.append(a["id"])
        _ensure_artist_genres_cached(all_artist_ids)

        for item in items:
            if not item or not isinstance(item, dict) or not item.get("id"):
                continue
            if item["id"] in used_ids:
                continue

            track_obj = {
                "id": item["id"],
                "name": item.get("name", ""),
                "artists": [{"id": a["id"], "name": a["name"]} for a in item.get("artists", []) if a],
                "external_urls": {"spotify": item.get("external_urls", {}).get("spotify", "")},
                "explicit": item.get("explicit", False),
                "album": {"name": (item.get("album") or {}).get("name", "")}
            }
            artist_ids = [a.get("id") for a in (item.get("artists") or []) if a and a.get("id")]

            if required_lang and not _track_matches_language(track_obj, required_lang):
                continue
            if required_genres and not _artist_matches_genre_strict(artist_ids, required_genres):
                continue

            tracks.append({"track": track_obj})
            used_ids.add(item["id"])

        if len(tracks) >= limit:
            break

    return tracks, used_ids

def search_playlists_and_collect_tracks(
    query: str,
    per_playlist_limit: int,
    used_ids: Set[str],
    required_lang: Optional[str],
    required_genres: List[str],
    max_playlists: int,
    market: Optional[str],
    tries: int = 2
) -> Tuple[List[dict], Set[str]]:
    out: List[dict] = []
    for _ in range(max(1, tries)):
        params = {"q": query, "type": "playlist", "limit": max_playlists}
        if market:
            params["market"] = market
        params["offset"] = _rand_offset(200)

        data = sp_get("https://api.spotify.com/v1/search", params=params)
        if not data or "playlists" not in data:
            continue

        playlist_items = data["playlists"].get("items", []) or []
        if not playlist_items:
            continue

        for pl in playlist_items[:max_playlists]:
            if not pl or not isinstance(pl, dict):
                continue
            pl_id = pl.get("id")
            if not pl_id:
                continue
            tracks_params = {"limit": per_playlist_limit}
            if market:
                tracks_params["market"] = market
            tracks_params["offset"] = _rand_offset(200)

            tracks_data = sp_get(f"https://api.spotify.com/v1/playlists/{pl_id}/tracks", params=tracks_params)
            if not tracks_data or "items" not in tracks_data:
                continue

            playlist_artist_ids: List[str] = []
            for it in tracks_data.get("items", []) or []:
                tr = it.get("track") if it else None
                if not tr or not tr.get("id"):
                    continue
                for a in (tr.get("artists") or []):
                    if a and a.get("id"):
                        playlist_artist_ids.append(a["id"])
            _ensure_artist_genres_cached(playlist_artist_ids)

            for it in tracks_data.get("items", []) or []:
                tr = it.get("track") if it else None
                if not tr or not tr.get("id"):
                    continue
                tid = tr["id"]
                if tid in used_ids:
                    continue

                track_obj = {
                    "id": tid,
                    "name": tr.get("name", ""),
                    "artists": [{"id": a["id"], "name": a["name"]} for a in tr.get("artists", []) if a],
                    "external_urls": {"spotify": tr.get("external_urls", {}).get("spotify", "")},
                    "explicit": tr.get("explicit", False),
                    "album": {"name": (tr.get("album") or {}).get("name", "")}
                }
                artist_ids = [a.get("id") for a in (tr.get("artists") or []) if a and a.get("id")]

                if required_lang and not _track_matches_language(track_obj, required_lang):
                    continue
                if required_genres and not _artist_matches_genre_strict(artist_ids, required_genres):
                    continue

                out.append({"track": track_obj})
                used_ids.add(tid)

        if out:
            break

    return out, used_ids

# ----------------------------
# Recommendations (market-aware)
# ----------------------------
def get_available_genre_seeds() -> Set[str]:
    data = sp_get("https://api.spotify.com/v1/recommendations/available-genre-seeds")
    return set((data or {}).get("genres", []))

def recommend_by_genre(required_genres: List[str], limit: int, used_ids: Set[str], market: Optional[str]) -> Tuple[List[dict], Set[str]]:
    out: List[dict] = []
    seeds = get_available_genre_seeds()
    if not seeds or not required_genres:
        return out, used_ids

    seed = None
    for g in required_genres:
        for s in seeds:
            if _norm(g) in _norm(s) or _norm(s) in _norm(g):
                seed = s
                break
        if seed:
            break
    if not seed:
        return out, used_ids

    data = sp_get("https://api.spotify.com/v1/recommendations", params={
        "limit": min(limit, 100),
        "seed_genres": seed,
        "market": market or DEFAULT_MARKET
    })

    for tr in (data or {}).get("tracks", []) or []:
        if not tr or not isinstance(tr, dict) or not tr.get("id"):
            continue
        tid = tr["id"]
        if tid in used_ids:
            continue
        track_obj = {
            "id": tid,
            "name": tr.get("name", ""),
            "artists": [{"id": a["id"], "name": a["name"]} for a in tr.get("artists", []) if a],
            "external_urls": {"spotify": tr.get("external_urls", {}).get("spotify", "")},
            "explicit": tr.get("explicit", False),
            "album": {"name": (tr.get("album") or {}).get("name", "")}
        }
        artist_ids = [a.get("id") for a in (tr.get("artists") or []) if a and a.get("id")]
        if not _artist_matches_genre_strict(artist_ids, required_genres):
            continue
        out.append({"track": track_obj})
        used_ids.add(tid)

    return out, used_ids

# ----------------------------
# Audio Features
# ----------------------------
def fetch_audio_features(track_ids: List[str]) -> Dict[str, Dict]:
    if not track_ids:
        return {}
    feats: Dict[str, Dict] = {}
    for i in range(0, len(track_ids), 100):
        chunk = track_ids[i:i+100]
        data = sp_get("https://api.spotify.com/v1/audio-features", params={"ids": ",".join(chunk)})
        for f in (data or {}).get("audio_features", []) or []:
            if not f or not f.get("id"):
                continue
            feats[f["id"]] = {
                "energy": f.get("energy"),
                "valence": f.get("valence"),
                "danceability": f.get("danceability"),
                "tempo": f.get("tempo"),
                "instrumentalness": f.get("instrumentalness"),
            }
    return feats

# ----------------------------
# Re-ranking (mood/context + vibe/genre boosts)
# ----------------------------
def _vibe_boost(track: dict, artist_genres: Set[str], vibe_tokens: List[str], required_genres: List[str]) -> float:
    boost = 0.0
    name = _norm(track.get("name", ""))
    album_name = _norm((track.get("album") or {}).get("name", ""))
    artist_names = " ".join([_norm(a.get("name","")) for a in (track.get("artists") or [])])

    for vt in vibe_tokens:
        if vt and (vt in name or vt in artist_names or vt in album_name):
            boost += 0.02
    for g in required_genres:
        if any(g in ag or ag in g for ag in artist_genres):
            boost += 0.05
        if g in name or g in artist_names or g in album_name:
            boost += 0.03
    return boost

def rerank_with_mood(final_tracks: List[dict], mood: Optional[str], context: Optional[str],
                     exclude_explicit: bool, vibe_text: str, required_genres: List[str]) -> List[dict]:
    if not final_tracks:
        return final_tracks

    if exclude_explicit:
        final_tracks = [t for t in final_tracks if not t.get("track", {}).get("explicit", False)]
        if not final_tracks:
            return []

    ids = [t["track"]["id"] for t in final_tracks if t.get("track", {}).get("id")]
    feats = fetch_audio_features(ids)

    targets = mood_targets(_norm(mood or ""), _norm(context or ""))
    base_scores = score_tracks(targets, feats)

    all_artist_ids: List[str] = []
    for t in final_tracks:
        for a in t["track"].get("artists", []):
            if a.get("id"):
                all_artist_ids.append(a["id"])
    _ensure_artist_genres_cached(all_artist_ids)

    vibe_tokens = tokenize(vibe_text)
    for t in final_tracks:
        tid = t["track"]["id"]
        f = feats.get(tid, {})
        base = float(base_scores.get(tid, 0.0))
        ag: Set[str] = set()
        for a in t["track"].get("artists", []):
            ag.update(ARTIST_GENRE_CACHE.get(a.get("id",""), []))
        b = _vibe_boost(t["track"], ag, vibe_tokens, required_genres)
        t["score"] = base + b + random.uniform(-0.01, 0.01)
        t["reason"] = reason_string(f) if f else "features unavailable"

    final_tracks.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return final_tracks

# ----------------------------
# Market selection (NEW with language hints)
# ----------------------------
LANG_MARKETS_HINT = {
    # existing region logic
    "sinhala": ["LK", "IN"],
    "tamil":   ["LK", "IN"],
    "hindi":   ["IN"],
    "english": ["US", "GB"],
    # NEW language → market priorities
    "korean":      ["KR"],
    "japanese":    ["JP"],
    "spanish":     ["ES", "MX", "US"],
    "portuguese":  ["BR", "PT"],
    "french":      ["FR", "CA"],
    "german":      ["DE", "AT", "CH"],
    "arabic":      ["SA", "AE", "EG"],
    "turkish":     ["TR"],
    "russian":     ["RU"],
    "indonesian":  ["ID"],
    "thai":        ["TH"],
    # Spotify not in mainland China; use HK/TW/SG for “chinese”
    "chinese":     ["TW", "HK", "SG"],
}

def _pick_markets(desired_lang: Optional[str]) -> List[str]:
    """
    Build a de-duplicated priority list of markets to query, combining:
      1) language hints (if we have a language)
      2) SPOTIFY_MARKETS from .env (user preference)
      3) DEFAULT_MARKET as final fallback
    """
    lang_hint = LANG_MARKETS_HINT.get((desired_lang or "").lower(), [])
    out: List[str] = []
    for m in lang_hint + MARKETS_PREF + [DEFAULT_MARKET]:
        m = (m or "").strip().upper()
        if m and m not in out:
            out.append(m)
    return out

# ----------------------------
# Generate Playlist from User Settings
# ----------------------------
def generate_playlist_from_user_settings(
    vibe_description: str,
    mood: str | None = None,
    activity: str | None = None,
    genre_or_language: str | None = None,
    tracks_per_playlist: int = 15,
    used_ids: set | None = None,
    seed: int | None = None,
    exclude_explicit: bool = False
):
    if used_ids is None:
        used_ids = set()

    desired_lang, desired_genres = parse_language_and_genres(genre_or_language)

    # If user didn’t specify a language, try inferring from the vibe text
    if not desired_lang:
        inferred = _detect_lang_from_text(vibe_description or "")
        if inferred:
            desired_lang = inferred

    # choose markets to try in order (based on language + env)
    markets = _pick_markets(desired_lang)

    final_tracks: list = []
    target = tracks_per_playlist
    half_target = max(1, target // 2)

    variants = build_query_variants(
        vibe_description=vibe_description,
        mood=mood,
        activity=activity,
        genre_or_language=genre_or_language
    )

    # Pass 1: strict search (multi-offset) across markets
    for q in variants:
        if len(final_tracks) >= target:
            break
        for mkt in markets:
            fetched, used_ids = search_tracks(
                query=q, limit=max(30, target * 3), used_ids=used_ids,
                required_lang=desired_lang, required_genres=desired_genres,
                market=mkt, tries=3
            )
            final_tracks.extend([t for t in fetched if t not in final_tracks])
            if len(final_tracks) >= target:
                break

    # Pass 2: playlist mining (strict) across markets
    if len(final_tracks) < target:
        for q in variants:
            if len(final_tracks) >= target:
                break
            for mkt in markets:
                pl_tracks, used_ids = search_playlists_and_collect_tracks(
                    query=q, per_playlist_limit=30, used_ids=used_ids,
                    required_lang=desired_lang, required_genres=desired_genres,
                    max_playlists=3, market=mkt, tries=2
                )
                final_tracks.extend([t for t in pl_tracks if t not in final_tracks])
                if len(final_tracks) >= target:
                    break

    # Pass 3: genre-based recommendations (market-aware, still strict on genre)
    if len(final_tracks) < target and desired_genres:
        for mkt in markets:
            if len(final_tracks) >= target:
                break
            recs, used_ids = recommend_by_genre(
                required_genres=desired_genres,
                limit=target - len(final_tracks),
                used_ids=used_ids,
                market=mkt
            )
            final_tracks.extend([t for t in recs if t not in final_tracks])

    # Pass 4: relax ONLY language (keep genres strict) across markets
    if len(final_tracks) < half_target and desired_lang:
        for q in variants:
            if len(final_tracks) >= target:
                break
            for mkt in markets:
                fetched, used_ids = search_tracks(
                    query=q, limit=max(30, target * 2), used_ids=used_ids,
                    required_lang=None,
                    required_genres=desired_genres,
                    market=mkt, tries=2
                )
                final_tracks.extend([t for t in fetched if t not in final_tracks])
                if len(final_tracks) >= target:
                    break

    # Pass 5: language-only requests (no genres) → markets already prioritized
    if len(final_tracks) < half_target and not desired_genres and desired_lang:
        for q in variants:
            if len(final_tracks) >= target:
                break
            for mkt in markets:
                fetched, used_ids = search_tracks(
                    query=q, limit=max(30, target * 2), used_ids=used_ids,
                    required_lang=desired_lang, required_genres=[],
                    market=mkt, tries=2
                )
                final_tracks.extend([t for t in fetched if t not in final_tracks])
                if len(final_tracks) >= target:
                    break

    if not final_tracks:
        return [], used_ids

    ranked = rerank_with_mood(
        final_tracks,
        mood,
        activity,
        exclude_explicit=exclude_explicit,
        vibe_text=vibe_description or "",
        required_genres=desired_genres
    )
    if not ranked:
        return [], used_ids
    return ranked[:target], used_ids
