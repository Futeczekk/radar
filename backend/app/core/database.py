import sqlite3
from datetime import datetime, timezone


DB_PATH = "/data/radar.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS repositories (
                repository TEXT PRIMARY KEY,
                latest_release TEXT,
                last_checked TEXT
            )
        """)


def get_previous_release(repository: str):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT latest_release FROM repositories WHERE repository = ?",
            (repository,)
        ).fetchone()

    return row[0] if row else None


def save_repository_state(repository: str, latest_release):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO repositories (
                repository,
                latest_release,
                last_checked
            )
            VALUES (?, ?, ?)
            ON CONFLICT(repository) DO UPDATE SET
                latest_release = excluded.latest_release,
                last_checked = excluded.last_checked
        """, (
            repository,
            latest_release,
            datetime.now(timezone.utc).isoformat()
        ))
