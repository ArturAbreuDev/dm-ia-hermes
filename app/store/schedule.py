"""Fila de posts agendados (feed / reels / story / prévias no Telegram)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.store.memory import _postgres, _postgres_dsn, _sqlite

KINDS = frozenset({"feed", "reels", "story", "previas"})

_TABLE_PG = """
CREATE TABLE IF NOT EXISTS scheduled_posts (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    media_url TEXT NOT NULL,
    caption TEXT NOT NULL DEFAULT '',
    share_to_feed BOOLEAN NOT NULL DEFAULT TRUE,
    scheduled_for TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    ig_media_id TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ
)
"""

_TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS scheduled_posts (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    media_url TEXT NOT NULL,
    caption TEXT NOT NULL DEFAULT '',
    share_to_feed INTEGER NOT NULL DEFAULT 1,
    scheduled_for TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    ig_media_id TEXT,
    created_at TEXT NOT NULL,
    published_at TEXT
)
"""


def _row_pg(r) -> dict[str, Any]:
    return {
        "id": r[0],
        "kind": r[1],
        "media_url": r[2],
        "caption": r[3] or "",
        "share_to_feed": bool(r[4]),
        "scheduled_for": r[5],
        "status": r[6],
        "error": r[7],
        "ig_media_id": r[8],
        "created_at": r[9],
        "published_at": r[10],
    }


def create(
    *,
    kind: str,
    media_url: str,
    caption: str = "",
    share_to_feed: bool = True,
    scheduled_for: datetime,
) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("kind inválido")
    if scheduled_for.tzinfo is None:
        scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)
    post_id = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                INSERT INTO scheduled_posts
                    (id, kind, media_url, caption, share_to_feed, scheduled_for,
                     status, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,'pending',%s)
                """,
                (
                    post_id,
                    kind,
                    media_url,
                    caption or "",
                    share_to_feed,
                    scheduled_for,
                    now,
                ),
            )
        return get(post_id) or {"id": post_id}

    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        conn.execute(
            """
            INSERT INTO scheduled_posts
                (id, kind, media_url, caption, share_to_feed, scheduled_for,
                 status, created_at)
            VALUES (?,?,?,?,?,?, 'pending', ?)
            """,
            (
                post_id,
                kind,
                media_url,
                caption or "",
                1 if share_to_feed else 0,
                scheduled_for.isoformat(),
                now.isoformat(),
            ),
        )
    return get(post_id) or {"id": post_id}


def get(post_id: str) -> dict[str, Any] | None:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                "SELECT id, kind, media_url, caption, share_to_feed, scheduled_for, "
                "status, error, ig_media_id, created_at, published_at "
                "FROM scheduled_posts WHERE id = %s",
                (post_id,),
            )
            row = cur.fetchone()
        return _row_pg(row) if row else None
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        row = conn.execute(
            "SELECT * FROM scheduled_posts WHERE id = ?", (post_id,)
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "kind": row["kind"],
        "media_url": row["media_url"],
        "caption": row["caption"] or "",
        "share_to_feed": bool(row["share_to_feed"]),
        "scheduled_for": row["scheduled_for"],
        "status": row["status"],
        "error": row["error"],
        "ig_media_id": row["ig_media_id"],
        "created_at": row["created_at"],
        "published_at": row["published_at"],
    }


def list_recent(limit: int = 40) -> list[dict[str, Any]]:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                SELECT id, kind, media_url, caption, share_to_feed, scheduled_for,
                       status, error, ig_media_id, created_at, published_at
                FROM scheduled_posts
                ORDER BY scheduled_for DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [_row_pg(r) for r in cur.fetchall()]
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        rows = conn.execute(
            "SELECT * FROM scheduled_posts ORDER BY scheduled_for DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "kind": r["kind"],
            "media_url": r["media_url"],
            "caption": r["caption"] or "",
            "share_to_feed": bool(r["share_to_feed"]),
            "scheduled_for": r["scheduled_for"],
            "status": r["status"],
            "error": r["error"],
            "ig_media_id": r["ig_media_id"],
            "created_at": r["created_at"],
            "published_at": r["published_at"],
        }
        for r in rows
    ]


def due(now: datetime | None = None) -> list[dict[str, Any]]:
    agora = now or datetime.now(timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=timezone.utc)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                SELECT id, kind, media_url, caption, share_to_feed, scheduled_for,
                       status, error, ig_media_id, created_at, published_at
                FROM scheduled_posts
                WHERE status = 'pending' AND scheduled_for <= %s
                ORDER BY scheduled_for ASC
                LIMIT 20
                """,
                (agora,),
            )
            return [_row_pg(r) for r in cur.fetchall()]
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        rows = conn.execute(
            """
            SELECT * FROM scheduled_posts
            WHERE status = 'pending' AND scheduled_for <= ?
            ORDER BY scheduled_for ASC
            LIMIT 20
            """,
            (agora.isoformat(),),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "kind": r["kind"],
            "media_url": r["media_url"],
            "caption": r["caption"] or "",
            "share_to_feed": bool(r["share_to_feed"]),
            "scheduled_for": r["scheduled_for"],
            "status": r["status"],
            "error": r["error"],
            "ig_media_id": r["ig_media_id"],
            "created_at": r["created_at"],
            "published_at": r["published_at"],
        }
        for r in rows
    ]


def mark(
    post_id: str,
    *,
    status: str,
    error: str | None = None,
    ig_media_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                UPDATE scheduled_posts
                SET status = %s,
                    error = %s,
                    ig_media_id = COALESCE(%s, ig_media_id),
                    published_at = CASE WHEN %s = 'published' THEN %s ELSE published_at END
                WHERE id = %s
                """,
                (status, error, ig_media_id, status, now, post_id),
            )
        return
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        conn.execute(
            """
            UPDATE scheduled_posts
            SET status = ?, error = ?,
                ig_media_id = COALESCE(?, ig_media_id),
                published_at = CASE WHEN ? = 'published' THEN ? ELSE published_at END
            WHERE id = ?
            """,
            (
                status,
                error,
                ig_media_id,
                status,
                now.isoformat(),
                post_id,
            ),
        )


def cancel(post_id: str) -> bool:
    item = get(post_id)
    if not item or item["status"] not in {"pending", "failed"}:
        return False
    mark(post_id, status="cancelled")
    return True
