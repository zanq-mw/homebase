import os
import sqlite3
from flask import g

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'homebase.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        _ensure_schema(g.db)
    return g.db


def _ensure_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS comments (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            page_type     TEXT    NOT NULL,
            page_id       INTEGER NOT NULL,
            name          TEXT    NOT NULL DEFAULT '',
            body          TEXT    NOT NULL,
            ip_hash       TEXT    NOT NULL,
            created_at    TEXT    NOT NULL,
            likes         INTEGER NOT NULL DEFAULT 0,
            session_token TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_comments_page
            ON comments(page_type, page_id, created_at DESC);
    """)
    # Migrate existing DBs that predate the session_token column
    try:
        conn.execute("ALTER TABLE comments ADD COLUMN session_token TEXT")
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.commit()
