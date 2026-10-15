"""Quem deu Start no bot de vendas — fila de remarketing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.store.memory import _postgres, _postgres_dsn, _sqlite

_TABLE_PG = """
CREATE TABLE IF NOT EXISTS telegram_leads (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    rmk_step INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL,
    last_rmk_at TIMESTAMPTZ,
    next_rmk_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL
)
"""

_TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS telegram_leads (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    rmk_step INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    last_rmk_at TEXT,
    next_rmk_at TEXT,
    updated_at TEXT NOT NULL
)
"""


def _row(r) -> dict[str, Any]:
    if r is None:
        return {}
    if hasattr(r, "keys"):
        return {
            "user_id": r["user_id"],
            "username": r["username"],
            "first_name": r["first_name"],
            "status": r["status"],
            "rmk_step": int(r["rmk_step"] or 0),
            "started_at": r["started_at"],
            "last_rmk_at": r["last_rmk_at"],
            "next_rmk_at": r["next_rmk_at"],
        }
    return {
        "user_id": r[0],
        "username": r[1],
        "first_name": r[2],
        "status": r[3],
        "rmk_step": int(r[4] or 0),
        "started_at": r[5],
        "last_rmk_at": r[6],
        "next_rmk_at": r[7],
    }


def get(user_id: str) -> dict[str, Any] | None:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                "SELECT user_id, username, first_name, status, rmk_step, "
                "started_at, last_rmk_at, next_rmk_at "
                "FROM telegram_leads WHERE user_id = %s",
                (str(user_id),),
            )
            row = cur.fetchone()
        return _row(row) if row else None
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        row = conn.execute(
            "SELECT user_id, username, first_name, status, rmk_step, "
            "started_at, last_rmk_at, next_rmk_at "
            "FROM telegram_leads WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
    return _row(row) if row else None


def upsert_start(
    user_id: str,
    *,
    username: str | None,
    first_name: str | None,
    next_rmk_at: datetime,
) -> dict[str, Any]:
    agora = datetime.now(timezone.utc)
    if next_rmk_at.tzinfo is None:
        next_rmk_at = next_rmk_at.replace(tzinfo=timezone.utc)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                INSERT INTO telegram_leads
                    (user_id, username, first_name, status, rmk_step,
                     started_at, last_rmk_at, next_rmk_at, updated_at)
                VALUES (%s,%s,%s,'active',0,%s,NULL,%s,%s)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    status = CASE
                        WHEN telegram_leads.status IN ('paid','stopped')
                        THEN telegram_leads.status
                        ELSE 'active'
                    END,
                    next_rmk_at = CASE
                        WHEN telegram_leads.status IN ('paid','stopped')
                        THEN telegram_leads.next_rmk_at
                        WHEN telegram_leads.next_rmk_at IS NOT NULL
                        THEN telegram_leads.next_rmk_at
                        ELSE EXCLUDED.next_rmk_at
                    END,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    str(user_id),
                    username,
                    first_name,
                    agora,
                    next_rmk_at,
                    agora,
                ),
            )
        return get(user_id) or {"user_id": str(user_id)}
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        conn.execute(
            """
            INSERT INTO telegram_leads
                (user_id, username, first_name, status, rmk_step,
                 started_at, last_rmk_at, next_rmk_at, updated_at)
            VALUES (?,?,?,'active',0,?,NULL,?,?)
            ON CONFLICT (user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                status = CASE
                    WHEN telegram_leads.status IN ('paid','stopped')
                    THEN telegram_leads.status
                    ELSE 'active'
                END,
                next_rmk_at = CASE
                    WHEN telegram_leads.status IN ('paid','stopped')
                    THEN telegram_leads.next_rmk_at
                    WHEN telegram_leads.next_rmk_at IS NOT NULL
                    THEN telegram_leads.next_rmk_at
                    ELSE excluded.next_rmk_at
                END,
                updated_at = excluded.updated_at
            """,
            (
                str(user_id),
                username,
                first_name,
                agora.isoformat(),
                next_rmk_at.isoformat(),
                agora.isoformat(),
            ),
        )
    return get(user_id) or {"user_id": str(user_id)}


def mark(
    user_id: str,
    *,
    status: str | None = None,
    rmk_step: int | None = None,
    next_rmk_at: datetime | None = None,
) -> None:
    agora = datetime.now(timezone.utc)
    atual = get(user_id)
    if not atual:
        return
    novo_status = status or atual["status"]
    novo_step = atual["rmk_step"] if rmk_step is None else rmk_step
    proximo = next_rmk_at
    if proximo is not None and proximo.tzinfo is None:
        proximo = proximo.replace(tzinfo=timezone.utc)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                UPDATE telegram_leads
                   SET status = %s,
                       rmk_step = %s,
                       last_rmk_at = %s,
                       next_rmk_at = COALESCE(%s, next_rmk_at),
                       updated_at = %s
                 WHERE user_id = %s
                """,
                (
                    novo_status,
                    novo_step,
                    agora,
                    proximo,
                    agora,
                    str(user_id),
                ),
            )
        return
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        conn.execute(
            """
            UPDATE telegram_leads
               SET status = ?,
                   rmk_step = ?,
                   last_rmk_at = ?,
                   next_rmk_at = COALESCE(?, next_rmk_at),
                   updated_at = ?
             WHERE user_id = ?
            """,
            (
                novo_status,
                novo_step,
                agora.isoformat(),
                proximo.isoformat() if proximo else None,
                agora.isoformat(),
                str(user_id),
            ),
        )


def mark_paid(user_id: str) -> None:
    mark(user_id, status="paid")


def reativar_exaustos(*, min_step: int, next_rmk_at: datetime) -> int:
    """Quem a fila antiga marcou stopped no último RMK volta pro loop diário."""
    if min_step < 1:
        return 0
    if next_rmk_at.tzinfo is None:
        next_rmk_at = next_rmk_at.replace(tzinfo=timezone.utc)
    agora = datetime.now(timezone.utc)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                UPDATE telegram_leads
                   SET status = 'active',
                       rmk_step = GREATEST(rmk_step - 1, %s),
                       next_rmk_at = %s,
                       updated_at = %s
                 WHERE status = 'stopped'
                   AND rmk_step >= %s
                """,
                (max(0, min_step - 1), next_rmk_at, agora, min_step),
            )
            return int(cur.rowcount or 0)
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        cur = conn.execute(
            """
            UPDATE telegram_leads
               SET status = 'active',
                   rmk_step = CASE WHEN rmk_step > 0 THEN rmk_step - 1 ELSE 0 END,
                   next_rmk_at = ?,
                   updated_at = ?
             WHERE status = 'stopped'
               AND rmk_step >= ?
            """,
            (next_rmk_at.isoformat(), agora.isoformat(), min_step),
        )
        return int(cur.rowcount or 0)


def due(now: datetime | None = None, limit: int = 20) -> list[dict[str, Any]]:
    agora = now or datetime.now(timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=timezone.utc)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                SELECT user_id, username, first_name, status, rmk_step,
                       started_at, last_rmk_at, next_rmk_at
                  FROM telegram_leads
                 WHERE status = 'active'
                   AND next_rmk_at IS NOT NULL
                   AND next_rmk_at <= %s
                 ORDER BY next_rmk_at ASC
                 LIMIT %s
                """,
                (agora, limit),
            )
            return [_row(r) for r in cur.fetchall()]
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        rows = conn.execute(
            """
            SELECT user_id, username, first_name, status, rmk_step,
                   started_at, last_rmk_at, next_rmk_at
              FROM telegram_leads
             WHERE status = 'active'
               AND next_rmk_at IS NOT NULL
               AND next_rmk_at <= ?
             ORDER BY next_rmk_at ASC
             LIMIT ?
            """,
            (agora.isoformat(), limit),
        ).fetchall()
    return [_row(r) for r in rows]
