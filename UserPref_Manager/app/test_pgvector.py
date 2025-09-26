# test_pgvector.py
import os, numpy as np, psycopg
conn = psycopg.connect(os.environ.get("DATABASE_URL","postgresql://postgres:Randunu0718@localhost:5432/music_ai"))
with conn, conn.cursor() as cur:
    cur.execute("SELECT 1")
    print("Connected OK")
    cur.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")
    print("pgvector installed:", cur.fetchone()[0])