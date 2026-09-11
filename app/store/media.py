from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.store.memory import _postgres, _postgres_dsn

_TABLE = """
CREATE TABLE IF NOT EXISTS audio_clips (
    id TEXT PRIMARY KEY,
    data BYTEA NOT NULL,
    mime TEXT NOT NULL DEFAULT 'audio/mpeg',
    created_at TIMESTAMPTZ NOT NULL
)
"""

_ADD_MIME = "ALTER TABLE audio_clips ADD COLUMN IF NOT EXISTS mime TEXT NOT NULL DEFAULT 'audio/mpeg'"

# Sem Postgres (execução local) guardamos em memória só para testes.
_local: dict[str, tuple[bytes, str]] = {}

RETENTION = timedelta(days=1)


def save_audio(data: bytes, mime: str) -> str:
    clip_id = uuid.uuid4().hex
    dsn = _postgres_dsn()
    if not dsn:
        _local[clip_id] = (data, mime)
        return clip_id

    now = datetime.now(timezone.utc)
    with _postgres(dsn) as conn, conn.cursor() as cur:
        cur.execute(_TABLE)
        cur.execute(_ADD_MIME)
        cur.execute(
            "INSERT INTO audio_clips (id, data, mime, created_at) VALUES (%s, %s, %s, %s)",
            (clip_id, data, mime, now),
        )
        cur.execute("DELETE FROM audio_clips WHERE created_at < %s", (now - RETENTION,))
    return clip_id


def get_audio(clip_id: str) -> tuple[bytes, str] | None:
    dsn = _postgres_dsn()
    if not dsn:
        return _local.get(clip_id)

    with _postgres(dsn) as conn, conn.cursor() as cur:
        cur.execute(_TABLE)
        cur.execute(_ADD_MIME)
        cur.execute("SELECT data, mime FROM audio_clips WHERE id = %s", (clip_id,))
        row = cur.fetchone()
    return (bytes(row[0]), row[1]) if row else None
