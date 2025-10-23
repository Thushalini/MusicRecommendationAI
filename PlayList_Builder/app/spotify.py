import os
import re
import random
import base64
import unicodedata
import requests
import time
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

MARKETS_PREF = [
    m.strip().upper()
    for m in (os.getenv("SPOTIFY_MARKETS", "") or "").split(",")
    if m.strip()
]

if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("Spotify API credentials not set. Please check your .env file.")

# ----------------------------
# Speed / Query Budget Controls
# ----------------------------
BUDGET_SECS = float(os.getenv("REC_BUDGET_SECS", "7.0"))
FILL_STOP_RATIO = float(os.getenv("REC_FILL_STOP_RATIO", "0.5"))
SEARCH_TRIES = int(os.getenv("REC_SEARCH_TRIES", "2"))
PLAYLIST_TRIES = int(os.getenv("REC_PLAYLIST_TRIES", "1"))
MAX_OFFSET_SEARCH = int(os.getenv("REC_MAX_OFFSET_SEARCH", "220"))
MAX_OFFSET_PL = int(os.getenv("REC_MAX_OFFSET_PL", "120"))
MAX_VARIANTS = int(os.getenv("REC_MAX_VARIANTS", "6"))

# ----------------------------
# HTTP session
# ----------------------------
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.25,
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
_WORD_RE = re.compile(r"[A-Za-z0-9\-']+")

def _rand_offset(max_offset: int = 500) -> int:
    return random.randint(0, max_offset)

def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").strip().lower()

def tokenize(text: str) -> List[str]:
    if not text:
        return []
    phrases = re.findall(r'"([^"]+)"', text)
    remainder = re.sub(r'"[^"]+"', ' ', text or '')
    # support hashtags as tokens
    remainder = re.sub(r"#", " ", remainder)
    words = _WORD_RE.findall(remainder)
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
    "sinhala": {"si", "sinhala", "sinhalese"},
    "tamil": {"ta", "tamil"},
    "hindi": {"hi", "hindi"},
    "english": {"en", "english"},
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

GENRE_ALIASES = {
    "lofi": {"lofi", "lo-fi", "lo_fi", "lowfi", "study beats"},
    "hip hop": {"hip hop", "hip-hop", "rap"},
    "r&b": {"r&b", "rnb", "r and b"},
    "edm": {"edm", "electronic", "dance"},
    "k-pop": {"k-pop", "kpop"},
    "j-pop": {"j-pop", "jpop"},
    "pop": {"pop", "synthpop", "electropop"},
    "rock": {"rock", "alt rock", "alternative", "alt-rock"},
    "indie": {"indie", "indie pop", "indie rock"},
    "classical": {"classical", "orchestral"},
    "jazz": {"jazz"},
    # treat high-level moods commonly typed in vibe box as soft genres for recall
    "chill": {"chill", "chillout"},
    "focus": {"focus", "study"},
    "party": {"party"},
    "workout": {"workout", "gym"},
    "sleep": {"sleep", "sleepy"},
}

def _genre_match_token_set(g: str) -> Set[str]:
    g = _norm(g)
    for canon, aliases in GENRE_ALIASES.items():
        if g == canon or g in aliases:
            return {canon, *aliases}
    return {g}

def _is_range(text: str, ranges: List[Tuple[int,int]]) -> bool:
    return any(lo <= ord(c) <= hi for c in text for (lo, hi) in ranges)

def _is_sinhala(text: str) -> bool: return _is_range(text, [(0x0D80, 0x0DFF)])
def _is_tamil(text: str) -> bool:   return _is_range(text, [(0x0B80, 0x0BFF)])
def _is_devanagari(text: str) -> bool:  return _is_range(text, [(0x0900, 0x097F)])
def _is_hangul(text: str) -> bool:      return _is_range(text, [(0x1100,0x11FF),(0x3130,0x318F),(0xAC00,0xD7AF)])
def _is_hiragana(text: str) -> bool:    return _is_range(text, [(0x3040,0x309F)])
def _is_katakana(text: str) -> bool:    return _is_range(text, [(0x30A0,0x30FF)])
def _is_cjk(text: str) -> bool:         return _is_range(text, [(0x4E00,0x9FFF)])
def _is_arabic_script(text: str) -> bool: return _is_range(text, [(0x0600,0x06FF),(0x0750,0x077F)])
def _is_thai_script(text: str) -> bool:   return _is_range(text, [(0x0E00,0x0E7F)])
def _is_cyrillic(text: str) -> bool:      return _is_range(text, [(0x0400,0x04FF)])

def _detect_lang_from_text(text: str) -> Optional[str]:
    if not text: return None
    if _is_sinhala(text): return "sinhala"
    if _is_tamil(text): return "tamil"
    if _is_devanagari(text): return "hindi"
    if _is_hangul(text): return "korean"
    if _is_hiragana(text) or _is_katakana(text): return "japanese"
    if _is_arabic_script(text): return "arabic"
    if _is_thai_script(text): return "thai"
    if _is_cyrillic(text): return "russian"
    if _is_cjk(text): return "chinese"
    return None

def parse_language_and_genres(text: Optional[str]) -> Tuple[Optional[str], List[str]]:
    if not text:
        return None, []
    raw = text.strip()
    phrases = re.findall(r'"([^"]+)"', raw)
    remainder = re.sub(r'"[^"]+"', ' ', raw)
    chunks = re.split(r"[,\|/]+", remainder)
    tokens: List[str] = []
    for c in chunks:
        c = _norm(c)
        if c:
            tokens.extend(re.findall(r"[a-z0-9\-\&]+", c))
    tokens.extend([_norm(p) for p in phrases if p.strip()])

    # stitch common multi-words
    fixed: List[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        nxt = tokens[i+1] if i+1 < len(tokens) else ""
        nxt2 = tokens[i+2] if i+2 < len(tokens) else ""
        if t == "hip" and nxt == "hop": fixed.append("hip hop"); i += 2; continue
        if t == "r" and nxt == "and" and nxt2 == "b": fixed.append("r&b"); i += 3; continue
        if t == "lo" and nxt == "fi": fixed.append("lofi"); i += 2; continue
        fixed.append(t); i += 1

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

    genres = list(dict.fromkeys(genres))
    return lang, genres

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
# Vibe/Genre query variants (single prompt)
# ----------------------------
def _build_query_variants_from_prompt(prompt: str, genres: List[str]) -> List[str]:
    toks = tokenize(prompt)
    # favor quoted phrases / first two tokens / genres
    variants: List[str] = []
    if len(toks) >= 2:
        variants.append(" ".join(toks[:2]))
    if toks:
        variants.append(toks[0])
    variants.extend(genres[:3])
    # add the raw prompt last
    if prompt:
        variants.append(prompt)
    # de-dup while preserving order
    seen, out = set(), []
    for q in variants:
        qn = _norm(q)
        if qn and qn not in seen:
            out.append(q)
            seen.add(qn)
    random.shuffle(out)
    return out[:MAX_VARIANTS] if len(out) > MAX_VARIANTS else out

# ----------------------------
# Search helpers
# ----------------------------
def search_tracks(query: str, limit: int, used_ids: Set[str],
                  required_lang: Optional[str], required_genres: List[str],
                  market: Optional[str], tries: int = 3) -> Tuple[List[dict], Set[str]]:
    tracks: List[dict] = []
    for _ in range(max(1, tries)):
        params = {"q": query, "type": "track", "limit": min(limit, 50)}
        if market:
            params["market"] = market
        params["offset"] = _rand_offset(MAX_OFFSET_SEARCH)

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
        params["offset"] = _rand_offset(MAX_OFFSET_PL)

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
            tracks_params = {
                "limit": per_playlist_limit,
                "fields": "items(track(id,name,explicit,external_urls,album(name),artists(id,name))),next",
            }
            if market:
                tracks_params["market"] = market
            tracks_params["offset"] = _rand_offset(MAX_OFFSET_PL)

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
        if not chunk:
            continue
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
# Re-ranking
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
        kept = [t for t in final_tracks if not t.get("track", {}).get("explicit", False)]
        final_tracks = kept or final_tracks
        if not final_tracks:
            return []

    all_artist_ids: List[str] = []
    for t in final_tracks:
        for a in t["track"].get("artists", []):
            if a.get("id"): all_artist_ids.append(a["id"])
    _ensure_artist_genres_cached(all_artist_ids)

    vibe_tokens = tokenize(vibe_text)
    for t in final_tracks:
        ag: Set[str] = set()
        for a in t["track"].get("artists", []):
            ag.update(ARTIST_GENRE_CACHE.get(a.get("id",""), []))
        t["score"] = _vibe_boost(t["track"], ag, vibe_tokens, required_genres) + random.uniform(-0.005, 0.005)

    final_tracks.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    shortlist = final_tracks[:60]

    ids = [t["track"]["id"] for t in shortlist if t.get("track", {}).get("id")]
    feats = fetch_audio_features(ids)

    # mood/context are optional; if not provided we still compute with neutral targets
    targets = mood_targets(_norm(mood or ""), _norm(context or ""))
    base_scores = score_tracks(targets, feats)

    ranked: List[dict] = []
    for t in shortlist:
        tid = t["track"]["id"]
        base = float(base_scores.get(tid, 0.0))
        t["score"] = base + (t.get("score", 0.0))
        f = feats.get(tid, {})
        t["reason"] = reason_string(f) if f else "features unavailable"
        ranked.append(t)

    ranked.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return ranked

# ----------------------------
# Market selection
# ----------------------------
LANG_MARKETS_HINT = {
    "sinhala": ["LK", "IN"],
    "tamil":   ["LK", "IN"],
    "hindi":   ["IN"],
    "english": ["US", "GB"],
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
    "chinese":     ["TW", "HK", "SG"],
}

def _pick_markets(desired_lang: Optional[str]) -> List[str]:
    lang_hint = LANG_MARKETS_HINT.get((desired_lang or "").lower(), [])
    out: List[str] = []
    for m in lang_hint + MARKETS_PREF + [DEFAULT_MARKET]:
        m = (m or "").strip().upper()
        if m and m not in out:
            out.append(m)
    return out

# ----------------------------
# PUBLIC: Build from a single prompt: "Describe your vibe and genre"
# ----------------------------
def generate_playlist_from_prompt(
    prompt: str,
    tracks_per_playlist: int = 15,
    exclude_explicit: bool = False,
    mood_hint: str | None = None  # optional; UI can pass None
):
    """
    Single-entry API for UI with one text box: "Describe your vibe and genre".
    Examples:
      - "moody late-night lofi, focus, english"
      - "Tamil romantic hip hop for gym"
      - "\"sunset drive\" indie pop"
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return [], set()

    desired_lang, possible_genres = parse_language_and_genres(prompt)
    # If not explicit, try script detection
    if not desired_lang:
        inferred = _detect_lang_from_text(prompt)
        if inferred:
            desired_lang = inferred

    # Filter genre candidates to canonical-ish words
    canonical_genres: List[str] = []
    for g in possible_genres:
        # keep if it matches a known alias group or looks genre-like (short tokens)
        if any(g in aliases or g == canon for canon, aliases in GENRE_ALIASES.items()):
            canonical_genres.append(g)
        elif len(g) <= 12 and g.isalpha():
            # allow soft "mood-genres" like chill/focus
            canonical_genres.append(g)
    # de-dup while keeping order
    seen = set(); canonical_genres = [x for x in canonical_genres if not (x in seen or seen.add(x))]

    # markets
    markets = _pick_markets(desired_lang)
    if not desired_lang and len(markets) > 2:
        markets = markets[:2]
    broad_fallback_markets: List[str] = []
    for m in ["US", "GB", "IN", DEFAULT_MARKET]:
        if m not in markets:
            broad_fallback_markets.append(m)

    # queries
    variants = _build_query_variants_from_prompt(prompt, canonical_genres)

    used_ids: Set[str] = set()
    final_tracks: List[dict] = []
    target = tracks_per_playlist
    half_target = max(1, target // 2)
    fill_cutoff = int(target * FILL_STOP_RATIO)

    start_ts = time.monotonic()
    def _time_up() -> bool:
        return (time.monotonic() - start_ts) >= BUDGET_SECS

    # Pass 1 — strict by lang+genres
    for q in variants:
        if len(final_tracks) >= target or _time_up():
            break
        for mkt in markets:
            fetched, used_ids = search_tracks(
                query=q,
                limit=max(20, target * 2),
                used_ids=used_ids,
                required_lang=desired_lang,
                required_genres=canonical_genres,
                market=mkt,
                tries=SEARCH_TRIES
            )
            final_tracks.extend([t for t in fetched if t not in final_tracks])
            if len(final_tracks) >= fill_cutoff or _time_up():
                break

    # Pass 2 — mine playlists
    if len(final_tracks) < target and not _time_up():
        for q in variants:
            if len(final_tracks) >= target or _time_up():
                break
            for mkt in markets:
                pl_tracks, used_ids = search_playlists_and_collect_tracks(
                    query=q,
                    per_playlist_limit=15,
                    used_ids=used_ids,
                    required_lang=desired_lang,
                    required_genres=canonical_genres,
                    max_playlists=2,
                    market=mkt,
                    tries=PLAYLIST_TRIES
                )
                final_tracks.extend([t for t in pl_tracks if t not in final_tracks])
                if len(final_tracks) >= fill_cutoff or _time_up():
                    break

    # Pass 3 — seed recommendations by genre
    if len(final_tracks) < target and canonical_genres and not _time_up():
        for mkt in markets:
            if len(final_tracks) >= target or _time_up():
                break
            recs, used_ids = recommend_by_genre(
                required_genres=canonical_genres,
                limit=target - len(final_tracks),
                used_ids=used_ids,
                market=mkt
            )
            final_tracks.extend([t for t in recs if t not in final_tracks])

    # Pass 4 — relax language only
    if len(final_tracks) < half_target and desired_lang and not _time_up():
        for q in variants:
            if len(final_tracks) >= target or _time_up():
                break
            for mkt in markets:
                fetched, used_ids = search_tracks(
                    query=q,
                    limit=max(20, target * 2),
                    used_ids=used_ids,
                    required_lang=None,
                    required_genres=canonical_genres,
                    market=mkt,
                    tries=max(1, SEARCH_TRIES - 1)
                )
                final_tracks.extend([t for t in fetched if t not in final_tracks])
                if len(final_tracks) >= fill_cutoff or _time_up():
                    break

    # Emergency — drop all constraints, broaden markets
    if not final_tracks and not _time_up():
        for q in variants[:3]:
            if _time_up():
                break
            for mkt in (markets + broad_fallback_markets)[:4]:
                fetched, used_ids = search_tracks(
                    query=q,
                    limit=max(20, target),
                    used_ids=used_ids,
                    required_lang=None,
                    required_genres=[],
                    market=mkt,
                    tries=1
                )
                final_tracks.extend([t for t in fetched if t not in final_tracks])
                if len(final_tracks) >= max(8, half_target) or _time_up():
                    break
            if len(final_tracks) >= max(8, half_target) or _time_up():
                break

    if not final_tracks:
        return [], used_ids

    ranked = rerank_with_mood(
        final_tracks=final_tracks,
        mood=mood_hint,            # can be None
        context=None,
        exclude_explicit=exclude_explicit,
        vibe_text=prompt,
        required_genres=canonical_genres
    )
    if not ranked:
        return [], used_ids
    return ranked[:target], used_ids

# ----------------------------
# BACKWARD-COMPAT: old multi-field entry (still available if used elsewhere)
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
    """
    Kept for compatibility. Prefer `generate_playlist_from_prompt(prompt, ...)`.
    """
    prompt = " ".join([x for x in [vibe_description, genre_or_language, mood, activity] if x])
    return generate_playlist_from_prompt(
        prompt=prompt,
        tracks_per_playlist=tracks_per_playlist,
        exclude_explicit=exclude_explicit
    )
