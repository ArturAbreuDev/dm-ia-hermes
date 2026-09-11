from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.store.memory import _postgres, _postgres_dsn, _sqlite

# O story some do Instagram em 24h, mas as pessoas comentam sobre ele por dias.
# Por isso a descrição fica guardada por bem mais tempo que a mídia.
RETENTION = timedelta(days=7)

_SQLITE = """
CREATE TABLE IF NOT EXISTS story_context (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

_PG = """
CREATE TABLE IF NOT EXISTS story_context (
    id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
)
"""


def save(entry_id: str, description: str, kind: str = "story") -> None:
    now = datetime.now(timezone.utc)
    corte = now - RETENTION
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_PG)
            cur.execute(
                """
                INSERT INTO story_context (id, description, kind, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET description = EXCLUDED.description
                """,
                (entry_id, description, kind, now),
            )
            cur.execute("DELETE FROM story_context WHERE created_at < %s", (corte,))
        return
    with _sqlite() as conn:
        conn.execute(_SQLITE)
        conn.execute(
            """
            INSERT INTO story_context (id, description, kind, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET description = excluded.description
            """,
            (entry_id, description, kind, now.isoformat()),
        )
        conn.execute("DELETE FROM story_context WHERE created_at < ?", (corte.isoformat(),))


def get(entry_id: str) -> str | None:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_PG)
            cur.execute("SELECT description FROM story_context WHERE id = %s", (entry_id,))
            row = cur.fetchone()
        return row[0] if row else None
    with _sqlite() as conn:
        conn.execute(_SQLITE)
        row = conn.execute(
            "SELECT description FROM story_context WHERE id = ?", (entry_id,)
        ).fetchone()
    return row["description"] if row else None


def delete(entry_id: str) -> None:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_PG)
            cur.execute("DELETE FROM story_context WHERE id = %s", (entry_id,))
        return
    with _sqlite() as conn:
        conn.execute(_SQLITE)
        conn.execute("DELETE FROM story_context WHERE id = ?", (entry_id,))


def recent(limit: int = 12) -> list[dict[str, str]]:
    """Do mais recente para o mais antigo, com quantos dias tem cada um."""
    agora = datetime.now(timezone.utc)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_PG)
            cur.execute(
                """
                SELECT id, description, kind, created_at
                FROM story_context
                WHERE kind <> 'meta'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = [(row[0], row[1], row[2], row[3]) for row in cur.fetchall()]
    else:
        with _sqlite() as conn:
            conn.execute(_SQLITE)
            raw = conn.execute(
                """
                SELECT id, description, kind, created_at
                FROM story_context
                WHERE kind <> 'meta'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        rows = [
            (
                item["id"],
                item["description"],
                item["kind"],
                datetime.fromisoformat(item["created_at"]),
            )
            for item in raw
        ]

    saida = []
    for entry_id, description, kind, created_at in rows:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        dias = (agora - created_at).days
        saida.append(
            {
                "id": entry_id,
                "description": description,
                "kind": kind,
                "quando": _quando(dias),
            }
        )
    return saida


def _quando(dias: int) -> str:
    if dias <= 0:
        return "hoje"
    if dias == 1:
        return "ontem"
    return f"há {dias} dias"
