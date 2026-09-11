from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings


def _connect() -> sqlite3.Connection:
    path: Path = get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            mid TEXT UNIQUE,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            sender_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def already_processed(mid: str | None) -> bool:
    if not mid:
        return False
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM messages WHERE mid = ?", (mid,)).fetchone()
        return row is not None


def save_message(sender_id: str, role: str, text: str, mid: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO messages (sender_id, mid, role, text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                sender_id,
                mid,
                role,
                text,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def get_history(sender_id: str, limit: int = 12) -> list[dict[str, str]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT role, text
            FROM messages
            WHERE sender_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (sender_id, limit),
        ).fetchall()
    history = [{"role": row["role"], "text": row["text"]} for row in reversed(rows)]
    return history


def save_lead(sender_id: str, data: dict) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO leads (sender_id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(sender_id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (sender_id, json.dumps(data, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
