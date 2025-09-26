# app/datastore.py

import os, json, numpy as np
from typing import Any, Dict, List, Optional, Tuple
import psycopg
from psycopg.rows import dict_row

from dotenv import load_dotenv
load_dotenv()

VECTOR_DIM = int(os.getenv("VECTOR_DIM", "64"))

def get_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set. Put it in .env or export it in the shell.")
    return psycopg.connect(url)

def to_pgvec(arr: np.ndarray) -> str:
    return "[" + ",".join(f"{float(x):.6f}" for x in arr.tolist()) + "]"

# --------- USERS / TRACKS ----------
def ensure_user(user_id: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO users(user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))

def upsert_track(track: Dict[str, Any]):
    """
    track dict keys expected: track_id, artist_id, name, release_year, duration_ms, popularity, audio_json, genres(list[str]), vec(np.ndarray)
    """
    with get_conn() as conn, conn.cursor() as cur:
        vec_txt = to_pgvec(track["vec"]) if isinstance(track.get("vec"), np.ndarray) else None
        cur.execute(
            """
            INSERT INTO tracks (track_id, artist_id, name, release_year, duration_ms, popularity, audio_json, genres, vec)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
            ON CONFLICT (track_id) DO UPDATE SET
              artist_id=EXCLUDED.artist_id, name=EXCLUDED.name, release_year=EXCLUDED.release_year,
              duration_ms=EXCLUDED.duration_ms, popularity=EXCLUDED.popularity, audio_json=EXCLUDED.audio_json,
              genres=EXCLUDED.genres, vec=EXCLUDED.vec
            """,
            (
                track["track_id"],
                track["artist_id"],
                track.get("name"),
                track.get("release_year"),
                track.get("duration_ms"),
                track.get("popularity"),
                json.dumps(track.get("audio_json", {})),
                track.get("genres", []),
                vec_txt,
            ),
        )

def upsert_artist(artist: Dict[str, Any]):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO artists (artist_id, name, genres)
            VALUES (%s, %s, %s)
            ON CONFLICT (artist_id) DO UPDATE SET
              name   = EXCLUDED.name,
              genres = EXCLUDED.genres
            """,
            (artist["artist_id"], artist.get("name"), artist.get("genres", [])),
        )

# --------- INTERACTIONS ----------
def log_interaction(ev: Dict[str, Any]):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO interactions (user_id, track_id, event, ts, ms_played, liked, skipped, source)
            VALUES (%s,%s,%s, COALESCE(%s, now()), %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                ev["user_id"],
                ev["track_id"],
                ev["event"],
                ev.get("ts"),
                ev.get("ms_played"),
                ev.get("liked"),
                ev.get("skipped"),
                ev.get("source"),
            ),
        )

def fetch_recent_user_events(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM interactions WHERE user_id=%s ORDER BY ts DESC LIMIT %s", (user_id, limit))
        return list(cur.fetchall())

# --------- PROFILES ----------
def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM user_profiles WHERE user_id=%s", (user_id,))
        return cur.fetchone()

def upsert_user_profile(user_id: str, long_vec: np.ndarray, genre_counts: Dict[str, float], mood_counts: Dict[str, float]):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_profiles(user_id, long_term_vec, genre_counts, mood_counts, last_updated)
            VALUES (%s, %s::vector, %s::jsonb, %s::jsonb, now())
            ON CONFLICT (user_id) DO UPDATE SET
              long_term_vec=EXCLUDED.long_term_vec,
              genre_counts=EXCLUDED.genre_counts,
              mood_counts=EXCLUDED.mood_counts,
              last_updated=now()
            """,
            (user_id, to_pgvec(long_vec), json.dumps(genre_counts), json.dumps(mood_counts)),
        )

def fetch_track_vectors(track_ids: List[str]) -> Dict[str, np.ndarray]:
    if not track_ids:
        return {}
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT track_id, vec FROM tracks WHERE track_id = ANY(%s)", (track_ids,))
        out: Dict[str, np.ndarray] = {}
        for tid, vec in cur.fetchall():
            if isinstance(vec, str):
                arr = np.fromstring(vec.strip("[]"), sep=",", dtype=float)
            else:
                arr = np.array(vec)
            out[tid] = arr
        return out

# --------- ANN search with filters ----------
def ann_by_user_vector(
    user_vec: np.ndarray,
    pool: int = 500,
    genre: Optional[str] = None,
    artist_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    vec_txt = to_pgvec(user_vec)
    where_clauses, params = [], []

    if genre:
        where_clauses.append("%s = ANY(genres)")
        params.append(genre)

    if artist_ids:
        where_clauses.append("artist_id = ANY(%s)")
        params.append(artist_ids)

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    sql = f"""
      SELECT track_id, artist_id, genres, vec
      FROM tracks
      {where}
      ORDER BY vec <-> %s::vector
      LIMIT %s
    """
    params += [vec_txt, pool]
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())

# --------- simple search (name) ----------
def search_tracks_by_name(q: str, limit: int = 25) -> List[Dict[str, Any]]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT t.track_id, t.name, a.name AS artist
            FROM tracks t
            LEFT JOIN artists a ON a.artist_id = t.artist_id
            WHERE t.name ILIKE %s
            ORDER BY t.popularity DESC NULLS LAST
            LIMIT %s
            """,
            (f"%{q}%", limit),
        )
        return list(cur.fetchall())


# ---- artist name → ids (best-effort) ----
from psycopg.rows import dict_row  # ensure this import exists at top

def artist_ids_from_names(names: List[str], limit_per_name: int = 3) -> List[str]:
    """Return a list of artist_ids matching the provided names (ILIKE)."""
    if not names:
        return []
    out: List[str] = []
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        for name in names:
            cur.execute(
                """
                SELECT artist_id
                FROM artists
                WHERE name ILIKE %s
                ORDER BY artist_id
                LIMIT %s
                """,
                (f"%{name.strip()}%", limit_per_name),
            )
            out.extend([r["artist_id"] for r in cur.fetchall()])
    # unique while preserving order
    seen, uniq = set(), []
    for a in out:
        if a not in seen:
            seen.add(a); uniq.append(a)
    return uniq
