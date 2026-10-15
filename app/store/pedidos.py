"""Pedidos do nosso bot (Start/PIX/pago), com nome completo e @."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.store.memory import _postgres, _postgres_dsn, _sqlite

_TABLE_PG = """
CREATE TABLE IF NOT EXISTS pedidos (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    nome TEXT,
    username TEXT,
    origem TEXT NOT NULL DEFAULT 'telegram',
    status TEXT NOT NULL DEFAULT 'start',
    amount TEXT,
    tx TEXT,
    produto TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
)
"""

_TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS pedidos (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    nome TEXT,
    username TEXT,
    origem TEXT NOT NULL DEFAULT 'telegram',
    status TEXT NOT NULL DEFAULT 'start',
    amount TEXT,
    tx TEXT,
    produto TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _row(r) -> dict[str, Any]:
    if r is None:
        return {}
    if hasattr(r, "keys"):
        return {
            "id": r["id"],
            "user_id": r["user_id"],
            "nome": r["nome"],
            "username": r["username"],
            "origem": r["origem"],
            "status": r["status"],
            "amount": r["amount"],
            "tx": r["tx"],
            "produto": r["produto"],
            "created_at": r["created_at"],
        }
    return {
        "id": r[0],
        "user_id": r[1],
        "nome": r[2],
        "username": r[3],
        "origem": r[4],
        "status": r[5],
        "amount": r[6],
        "tx": r[7],
        "produto": r[8],
        "created_at": r[9],
    }


def save(
    *,
    user_id: str,
    nome: str,
    username: str = "",
    origem: str = "telegram",
    status: str = "start",
    amount: str = "",
    tx: str = "",
    produto: str = "Acesso VIP",
    pedido_id: str | None = None,
) -> dict[str, Any]:
    agora = datetime.now(timezone.utc)
    pid = pedido_id or (f"tx:{tx}" if tx else f"u:{user_id}:{uuid4().hex[:8]}")
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                INSERT INTO pedidos
                    (id, user_id, nome, username, origem, status, amount, tx,
                     produto, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    nome = EXCLUDED.nome,
                    username = EXCLUDED.username,
                    origem = EXCLUDED.origem,
                    status = EXCLUDED.status,
                    amount = COALESCE(NULLIF(EXCLUDED.amount,''), pedidos.amount),
                    tx = COALESCE(NULLIF(EXCLUDED.tx,''), pedidos.tx),
                    produto = EXCLUDED.produto,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    pid,
                    str(user_id),
                    nome,
                    username,
                    origem,
                    status,
                    amount,
                    tx,
                    produto,
                    agora,
                    agora,
                ),
            )
        return {"id": pid}
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        conn.execute(
            """
            INSERT INTO pedidos
                (id, user_id, nome, username, origem, status, amount, tx,
                 produto, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (id) DO UPDATE SET
                user_id = excluded.user_id,
                nome = excluded.nome,
                username = excluded.username,
                origem = excluded.origem,
                status = excluded.status,
                amount = COALESCE(NULLIF(excluded.amount,''), pedidos.amount),
                tx = COALESCE(NULLIF(excluded.tx,''), pedidos.tx),
                produto = excluded.produto,
                updated_at = excluded.updated_at
            """,
            (
                pid,
                str(user_id),
                nome,
                username,
                origem,
                status,
                amount,
                tx,
                produto,
                agora.isoformat(),
                agora.isoformat(),
            ),
        )
    return {"id": pid}


def mark_status(*, tx: str = "", user_id: str = "", status: str) -> None:
    agora = datetime.now(timezone.utc)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            if tx:
                cur.execute(
                    "UPDATE pedidos SET status=%s, updated_at=%s WHERE tx=%s OR id=%s",
                    (status, agora, tx, f"tx:{tx}"),
                )
            elif user_id:
                cur.execute(
                    """
                    UPDATE pedidos SET status=%s, updated_at=%s
                     WHERE user_id=%s AND status IN ('start','pending')
                    """,
                    (status, agora, str(user_id)),
                )
        return
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        if tx:
            conn.execute(
                "UPDATE pedidos SET status=?, updated_at=? WHERE tx=? OR id=?",
                (status, agora.isoformat(), tx, f"tx:{tx}"),
            )
        elif user_id:
            conn.execute(
                """
                UPDATE pedidos SET status=?, updated_at=?
                 WHERE user_id=? AND status IN ('start','pending')
                """,
                (status, agora.isoformat(), str(user_id)),
            )


def listar(limit: int = 80) -> list[dict[str, Any]]:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                SELECT id, user_id, nome, username, origem, status, amount, tx,
                       produto, created_at
                  FROM pedidos
                 ORDER BY created_at DESC
                 LIMIT %s
                """,
                (limit,),
            )
            return [_row(r) for r in cur.fetchall()]
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        rows = conn.execute(
            """
            SELECT id, user_id, nome, username, origem, status, amount, tx,
                   produto, created_at
              FROM pedidos
             ORDER BY created_at DESC
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row(r) for r in rows]
