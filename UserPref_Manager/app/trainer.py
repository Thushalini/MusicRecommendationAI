# app/trainer.py
import json, numpy as np, pandas as pd, psycopg, os
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from typing import Any, Dict
from dotenv import load_dotenv
load_dotenv()

URL = os.environ["DATABASE_URL"]
VECTOR_DIM = int(os.getenv("VECTOR_DIM", "64"))

AUDIO_KEYS = ["danceability","energy","valence","tempo","acousticness",
              "instrumentalness","liveness","speechiness"]

def fetch_audio_df():
    with psycopg.connect(URL) as conn:
        df = pd.read_sql("SELECT track_id, audio_json FROM tracks WHERE audio_json IS NOT NULL", conn)
    rows = []
    for _, r in df.iterrows():
        a = r["audio_json"]
        # when using psycopg, audio_json arrives as dict already
        v = [a.get(k, 0.0) for k in AUDIO_KEYS]
        v[3] = v[3] / 250.0  # tempo scale to ~0-1
        rows.append([r["track_id"], *v])
    cols = ["track_id"] + AUDIO_KEYS
    return pd.DataFrame(rows, columns=cols)

def train_pca():
    df = fetch_audio_df()
    if df.empty:
        raise RuntimeError("No audio features found to train PCA.")
    X = df[AUDIO_KEYS].values.astype(float)

    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    pca = PCA(n_components=VECTOR_DIM).fit(Xs)

    # save params to DB models table
    meta = {
        "scaler_mean": np.asarray(scaler.mean_, dtype=float).tolist(),
        "scaler_scale": np.asarray(scaler.scale_, dtype=float).tolist(),
        "pca_components": np.asarray(pca.components_, dtype=float).tolist(),
        "pca_mean": np.asarray(pca.mean_, dtype=float).tolist(),
     }
    
    with psycopg.connect(URL) as conn, conn.cursor() as cur:
        cur.execute("""
          INSERT INTO models(model_name, artifact_path, meta)
          VALUES (%s,%s,%s::jsonb)
          ON CONFLICT (model_name) DO UPDATE SET meta=EXCLUDED.meta
        """, 
        ("pca_audio@latest", "", json.dumps(meta)))
        
    print("saved PCA model")

def embed_all_tracks():
    # load PCA params
    with psycopg.connect(URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT meta FROM models WHERE model_name=%s", ("pca_audio@latest",))
        row = cur.fetchone()
        if not row:
            raise RuntimeError("PCA model not found in DB")
        meta = row[0]
    mean = np.array(meta["scaler_mean"]); scale = np.array(meta["scaler_scale"])
    comps = np.array(meta["pca_components"]); pmean = np.array(meta["pca_mean"])

    with psycopg.connect(URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT track_id, audio_json FROM tracks WHERE audio_json IS NOT NULL")
        rows = cur.fetchall()

        def to_vec(a):
            v = np.array([a.get(k, 0.0) for k in AUDIO_KEYS], dtype=float)
            v[3] = v[3]/250.0
            Xs = (v - mean) / (scale + 1e-8)
            z = (Xs - pmean) @ comps.T
            # normalize to unit length
            z = z / (np.linalg.norm(z) + 1e-8)
            return "[" + ",".join(f"{float(x):.6f}" for x in z.tolist()) + "]"

        for tid, a in rows:
            vec_txt = to_vec(a)
            cur.execute("UPDATE tracks SET vec = %s::vector WHERE track_id=%s", (vec_txt, tid))
    print("embedded tracks")

if __name__ == "__main__":
    train_pca()
    embed_all_tracks()
    print("done")
