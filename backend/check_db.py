"""
Run this from your backend folder to inspect the database:
  python check_db.py
"""
import sqlite3, os, json

DB_PATH = "narrativeiq.db"

if not os.path.exists(DB_PATH):
    print("❌ narrativeiq.db not found — make sure you're in the backend folder")
    exit()

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("\n── USERS ─────────────────────────────────────")
for row in conn.execute("SELECT id, name, email, created_at, is_active FROM users"):
    print(f"  {row['id'][:8]}... | {row['name']} | {row['email']} | active={row['is_active']}")

print("\n── STORIES ───────────────────────────────────")
for row in conn.execute("SELECT id, user_id, series_title, status, episode_count, created_at FROM stories ORDER BY created_at DESC"):
    print(f"  {row['id'][:8]}... | {row['series_title']} | status={row['status']} | eps={row['episode_count']}")

print("\n── EPISODES (last 10) ────────────────────────")
for row in conn.execute("SELECT story_id, episode_number, title, emotion_score, cliffhanger_score FROM episodes ORDER BY rowid DESC LIMIT 10"):
    print(f"  story={row['story_id'][:8]}... | ep{row['episode_number']} {row['title']} | emotion={row['emotion_score']} cliff={row['cliffhanger_score']}")

print("\n── ANALYSIS ──────────────────────────────────")
for row in conn.execute("SELECT story_id, overall_arc_score, avg_cliffhanger, avg_drop_off FROM analysis"):
    print(f"  story={row['story_id'][:8]}... | arc={row['overall_arc_score']} cliff={row['avg_cliffhanger']} dropoff={row['avg_drop_off']}")

conn.close()
print("\n✅ Done")
