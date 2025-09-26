import psycopg, os, numpy as np
from dotenv import load_dotenv; load_dotenv()
url = os.environ["DATABASE_URL"]

with psycopg.connect(url) as conn, conn.cursor() as cur:
    # toy recall@10: last played should appear in recs for that user
    cur.execute("""
      WITH last_play AS (
        SELECT user_id, track_id
        FROM (
          SELECT user_id, track_id, ts, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY ts DESC) r
          FROM interactions) t WHERE r=1
      )
      SELECT COUNT(*) FROM last_play
    """)

    row = cur.fetchone()
    if not row:
        raise RuntimeError("PCA model not found in DB")
    meta = row[0]

    print("Users with events:", row)
