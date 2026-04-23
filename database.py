import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'lostfound.db')

if os.environ.get('VERCEL'):
    # On Vercel, move the DB to /tmp so it's writable
    TEMP_DB = '/tmp/lostfound.db'
    if not os.path.exists(TEMP_DB):
        import shutil
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, TEMP_DB)
    DB_PATH = TEMP_DB


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # ── Users ─────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            created_at    DATETIME DEFAULT (datetime('now','localtime'))
        )
    """)

    # ── Items ─────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            status       TEXT    NOT NULL CHECK(status IN ('Lost','Found')),
            title        TEXT    NOT NULL,
            description  TEXT    NOT NULL,
            category     TEXT    NOT NULL,
            location     TEXT    NOT NULL,
            image_path   TEXT,
            claim_status TEXT    NOT NULL DEFAULT 'Available'
                          CHECK(claim_status IN ('Available','Pending','Claimed')),
            claimant_id  INTEGER,
            created_at   DATETIME DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id)    REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (claimant_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"[✓] Database initialised at: {DB_PATH}")


if __name__ == '__main__':
    init_db()
