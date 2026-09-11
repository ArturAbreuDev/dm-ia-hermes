from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import get_settings

_POSTGRES_ENV_KEYS = (
    "DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_PRISMA_URL",
    "DATABASE_URL_UNPOOLED",
)


def _postgres_dsn() -> str | None:
    for key in _POSTGRES_ENV_KEYS:
        value = os.getenv(key)
        if value:
            return value
    return None


_SQLITE_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id TEXT NOT NULL,
        mid TEXT UNIQUE,
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS leads (
        sender_id TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
)

_POSTGRES_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS messages (
        id BIGSERIAL PRIMARY KEY,
        sender_id TEXT NOT NULL,
        mid TEXT UNIQUE,
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS messages_sender_idx ON messages (sender_id, id DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS leads (
        sender_id TEXT PRIMARY KEY,
        data JSONB NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
)

_pg_ready = False


@contextmanager
def _sqlite() -> Iterator[sqlite3.Connection]:
    path: Path = get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        for statement in _SQLITE_SCHEMA:
            conn.execute(statement)
        conn.commit()
        yield conn
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _postgres(dsn: str) -> Iterator[Any]:
    global _pg_ready
    import psycopg

    conn = psycopg.connect(dsn, autocommit=True)
    try:
        if not _pg_ready:
            with conn.cursor() as cur:
                for statement in _POSTGRES_SCHEMA:
                    cur.execute(statement)
            _pg_ready = True
        yield conn
    finally:
        conn.close()


def already_processed(mid: str | None) -> bool:
    if not mid:
        return False
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM messages WHERE mid = %s", (mid,))
            return cur.fetchone() is not None
    with _sqlite() as conn:
        return conn.execute("SELECT 1 FROM messages WHERE mid = ?", (mid,)).fetchone() is not None


def save_message(sender_id: str, role: str, text: str, mid: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (sender_id, mid, role, text, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (mid) DO NOTHING
                """,
                (sender_id, mid, role, text, now),
            )
        return
    with _sqlite() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO messages (sender_id, mid, role, text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sender_id, mid, role, text, now.isoformat()),
        )


def get_history(sender_id: str, limit: int = 12) -> list[dict[str, str]]:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, text
                FROM messages
                WHERE sender_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (sender_id, limit),
            )
            rows = [{"role": row[0], "text": row[1]} for row in cur.fetchall()]
        return list(reversed(rows))
    with _sqlite() as conn:
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
    return [{"role": row["role"], "text": row["text"]} for row in reversed(rows)]


def save_lead(sender_id: str, data: dict) -> None:
    now = datetime.now(timezone.utc)
    payload = json.dumps(data, ensure_ascii=False)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO leads (sender_id, data, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (sender_id) DO UPDATE SET
                    data = EXCLUDED.data,
                    updated_at = EXCLUDED.updated_at
                """,
                (sender_id, payload, now),
            )
        return
    with _sqlite() as conn:
        conn.execute(
            """
            INSERT INTO leads (sender_id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(sender_id) DO UPDATE SET
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (sender_id, payload, now.isoformat()),
        )
