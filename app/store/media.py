from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.store.memory import _postgres, _postgres_dsn

_TABLE = """
CREATE TABLE IF NOT EXISTS audio_clips (
    id TEXT PRIMARY KEY,
    data BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
)
"""

# Sem Postgres (execução local) guardamos em memória só para testes.
_local: dict[str, bytes] = {}

RETENTION = timedelta(days=1)


def save_audio(data: bytes) -> str:
    clip_id = uuid.uuid4().hex
    dsn = _postgres_dsn()
    if not dsn:
        _local[clip_id] = data
        return clip_id

    now = datetime.now(timezone.utc)
    with _postgres(dsn) as conn, conn.cursor() as cur:
        cur.execute(_TABLE)
        cur.execute(
            "INSERT INTO audio_clips (id, data, created_at) VALUES (%s, %s, %s)",
            (clip_id, data, now),
        )
        cur.execute("DELETE FROM audio_clips WHERE created_at < %s", (now - RETENTION,))
    return clip_id


def get_audio(clip_id: str) -> bytes | None:
    dsn = _postgres_dsn()
    if not dsn:
        return _local.get(clip_id)

    with _postgres(dsn) as conn, conn.cursor() as cur:
        cur.execute(_TABLE)
        cur.execute("SELECT data FROM audio_clips WHERE id = %s", (clip_id,))
        row = cur.fetchone()
    return bytes(row[0]) if row else None
