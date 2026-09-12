"""Quem está dentro do grupo do Telegram.

A Bot API não lista os membros de um grupo: só conta quantos são e lista os
administradores. Então a lista tem que ser construída na entrada, guardando
cada pessoa no momento em que ela entra. E o `user_id` é a única chave que
serve, porque não existe forma oficial de resolver um @ de pessoa para id.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.store.memory import _postgres, _postgres_dsn, _sqlite

logger = logging.getLogger(__name__)

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS telegram_members (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    status TEXT NOT NULL,
    joined_at TEXT,
    updated_at TEXT NOT NULL
)
"""

_POSTGRES_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS telegram_members (
        user_id TEXT PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        status TEXT NOT NULL,
        joined_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS telegram_members_username_idx
        ON telegram_members (lower(username))
    """,
)

# Status que significam "está dentro". Vem da doc oficial do ChatMember: os seis
# valores possíveis são creator, administrator, member, restricted, left e kicked.
DENTRO = {"creator", "administrator", "member"}


def _preparar(conn, postgres: bool) -> None:
    if postgres:
        with conn.cursor() as cur:
            for statement in _POSTGRES_SCHEMA:
                cur.execute(statement)
    else:
        conn.execute(_SQLITE_SCHEMA)


def save(user_id: str, status: str, username: str | None, first_name: str | None) -> None:
    agora = datetime.now(timezone.utc)
    entrou = agora if status in DENTRO else None
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn:
            _preparar(conn, True)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO telegram_members
                        (user_id, username, first_name, status, joined_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        status = EXCLUDED.status,
                        joined_at = COALESCE(telegram_members.joined_at, EXCLUDED.joined_at),
                        updated_at = EXCLUDED.updated_at
                    """,
                    (str(user_id), username, first_name, status, entrou, agora),
                )
        return
    with _sqlite() as conn:
        _preparar(conn, False)
        conn.execute(
            """
            INSERT INTO telegram_members
                (user_id, username, first_name, status, joined_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                status = excluded.status,
                joined_at = COALESCE(telegram_members.joined_at, excluded.joined_at),
                updated_at = excluded.updated_at
            """,
            (
                str(user_id),
                username,
                first_name,
                status,
                entrou.isoformat() if entrou else None,
                agora.isoformat(),
            ),
        )


def find_by_username(username: str) -> dict | None:
    """Procura pelo @ do Telegram, sem arroba e sem diferenciar maiúscula."""
    limpo = (username or "").strip().lstrip("@").lower()
    if not limpo:
        return None
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn:
            _preparar(conn, True)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, username, first_name, status
                      FROM telegram_members
                     WHERE lower(username) = %s
                    """,
                    (limpo,),
                )
                linha = cur.fetchone()
        if not linha:
            return None
        return {
            "user_id": linha[0],
            "username": linha[1],
            "first_name": linha[2],
            "status": linha[3],
        }
    with _sqlite() as conn:
        _preparar(conn, False)
        linha = conn.execute(
            """
            SELECT user_id, username, first_name, status
              FROM telegram_members
             WHERE lower(username) = ?
            """,
            (limpo,),
        ).fetchone()
    return dict(linha) if linha else None


def count_inside() -> int:
    marcadores = ", ".join("?" * len(DENTRO))
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn:
            _preparar(conn, True)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM telegram_members WHERE status = ANY(%s)",
                    (list(DENTRO),),
                )
                return int(cur.fetchone()[0])
    with _sqlite() as conn:
        _preparar(conn, False)
        linha = conn.execute(
            f"SELECT count(*) FROM telegram_members WHERE status IN ({marcadores})",
            tuple(DENTRO),
        ).fetchone()
    return int(linha[0])
