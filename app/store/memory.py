from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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


def message_activity(days: int = 7) -> list[dict]:
    """Uma linha por mensagem recente, para os relatórios agregarem como quiserem."""
    corte = datetime.now(timezone.utc) - timedelta(days=days)
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT sender_id, role, created_at, text
                FROM messages
                WHERE created_at >= %s
                ORDER BY created_at
                """,
                (corte,),
            )
            linhas = cur.fetchall()
        return [
            {"sender_id": r[0], "role": r[1], "created_at": r[2], "text": r[3]} for r in linhas
        ]
    with _sqlite() as conn:
        linhas = conn.execute(
            """
            SELECT sender_id, role, created_at, text
            FROM messages
            WHERE created_at >= ?
            ORDER BY created_at
            """,
            (corte.isoformat(),),
        ).fetchall()
    return [
        {
            "sender_id": r["sender_id"],
            "role": r["role"],
            "created_at": datetime.fromisoformat(r["created_at"]),
            "text": r["text"],
        }
        for r in linhas
    ]


def first_seen() -> dict[str, datetime]:
    """Momento da primeira mensagem de cada pessoa, para contar conversa nova."""
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT sender_id, MIN(created_at) FROM messages GROUP BY sender_id")
            return {r[0]: r[1] for r in cur.fetchall()}
    with _sqlite() as conn:
        linhas = conn.execute(
            "SELECT sender_id, MIN(created_at) AS primeira FROM messages GROUP BY sender_id"
        ).fetchall()
    return {r["sender_id"]: datetime.fromisoformat(r["primeira"]) for r in linhas}


def all_leads() -> dict[str, dict]:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT sender_id, data FROM leads")
            linhas = cur.fetchall()
        return {
            r[0]: (r[1] if isinstance(r[1], dict) else json.loads(r[1])) for r in linhas
        }
    with _sqlite() as conn:
        linhas = conn.execute("SELECT sender_id, data FROM leads").fetchall()
    return {r["sender_id"]: json.loads(r["data"]) for r in linhas}


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


def set_lead_flag(sender_id: str, campo: str, valor: bool = True) -> None:
    lead = get_lead(sender_id)
    if valor:
        lead[campo] = True
    else:
        lead.pop(campo, None)
    save_lead(sender_id, lead)


def bump_lead_counter(sender_id: str, campo: str) -> int:
    lead = get_lead(sender_id)
    valor = int(lead.get(campo, 0)) + 1
    lead[campo] = valor
    save_lead(sender_id, lead)
    return valor


def set_muted(sender_id: str, muted: bool) -> None:
    """Silencia um contato específico. Ele só é respondido se falar de compra."""
    lead = get_lead(sender_id)
    if muted:
        lead["muted"] = True
        lead["muted_at"] = datetime.now(timezone.utc).isoformat()
    else:
        lead.pop("muted", None)
        lead.pop("muted_at", None)
    save_lead(sender_id, lead)


def remember_username(sender_id: str, username: str | None) -> None:
    """Guarda o @ no lead, para as telas mostrarem nome em vez de número."""
    if not username:
        return
    lead = get_lead(sender_id)
    limpo = username.strip().lstrip("@")
    if not limpo or lead.get("username") == limpo:
        return
    lead["username"] = limpo
    save_lead(sender_id, lead)


def muted_leads() -> list[tuple[str, dict]]:
    """Contatos silenciados, do silenciamento mais recente para o mais antigo."""
    silenciados = [(s, d) for s, d in all_leads().items() if d.get("muted")]
    return sorted(silenciados, key=lambda par: par[1].get("muted_at") or "", reverse=True)


def mark_human_reply(sender_id: str) -> None:
    """Anota que a Lívia respondeu à mão agora, reiniciando a janela de silêncio."""
    lead = get_lead(sender_id)
    lead["human_reply_at"] = datetime.now(timezone.utc).isoformat()
    save_lead(sender_id, lead)


def human_pause_seconds(sender_id: str) -> float:
    """Quanto ainda falta para o bot poder voltar a falar. Zero se já pode."""
    quando = get_lead(sender_id).get("human_reply_at")
    if not quando:
        return 0.0
    try:
        marcado = datetime.fromisoformat(quando)
    except (TypeError, ValueError):
        return 0.0
    if marcado.tzinfo is None:
        marcado = marcado.replace(tzinfo=timezone.utc)
    janela = get_settings().human_takeover_minutes * 60
    passou = (datetime.now(timezone.utc) - marcado).total_seconds()
    return max(janela - passou, 0.0)


def last_assistant_text(sender_id: str) -> str | None:
    """Última coisa que saiu desta conta nesta conversa, para reconhecer o eco."""
    dsn = _postgres_dsn()
    consulta = """
        SELECT text FROM messages
         WHERE sender_id = {ph} AND role = 'assistant'
         ORDER BY id DESC LIMIT 1
    """
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(consulta.format(ph="%s"), (sender_id,))
            linha = cur.fetchone()
        return linha[0] if linha else None
    with _sqlite() as conn:
        linha = conn.execute(consulta.format(ph="?"), (sender_id,)).fetchone()
    return linha["text"] if linha else None


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
