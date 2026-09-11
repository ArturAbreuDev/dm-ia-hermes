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


def get_lead(sender_id: str) -> dict:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM leads WHERE sender_id = %s", (sender_id,))
            row = cur.fetchone()
        if not row:
            return {}
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    with _sqlite() as conn:
        row = conn.execute(
            "SELECT data FROM leads WHERE sender_id = ?", (sender_id,)
        ).fetchone()
    return json.loads(row["data"]) if row else {}


def mark_paid(sender_id: str) -> None:
    """Registra que a pessoa disse ter pago. A partir daí não se vende mais nada."""
    lead = get_lead(sender_id)
    if lead.get("paid"):
        return
    lead["paid"] = True
    lead["paid_at"] = datetime.now(timezone.utc).isoformat()
    save_lead(sender_id, lead)


def clear_paid(sender_id: str) -> None:
    lead = get_lead(sender_id)
    lead.pop("paid", None)
    lead.pop("paid_at", None)
    save_lead(sender_id, lead)


def bump_lead_counter(sender_id: str, campo: str) -> int:
    lead = get_lead(sender_id)
    valor = int(lead.get(campo, 0)) + 1
    lead[campo] = valor
    save_lead(sender_id, lead)
    return valor


def mark_link_sent(sender_id: str) -> None:
    """Guarda em que altura da conversa o link saiu, para saber quando desistir."""
    lead = get_lead(sender_id)
    if lead.get("link_sent"):
        return
    lead["link_sent"] = True
    lead["link_sent_at"] = int(lead.get("replies", 0))
    save_lead(sender_id, lead)


def is_paid(sender_id: str) -> bool:
    return bool(get_lead(sender_id).get("paid"))


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
