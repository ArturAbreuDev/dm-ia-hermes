"""Preferências que mudam sem redeploy.

A escolha de checkout (Straton ou Botgram) precisa virar na hora, pelo /diario,
sem esperar o próximo deploy. Por isso mora no banco e não na variável de ambiente.
"""

from __future__ import annotations

from app.store.memory import _postgres, _postgres_dsn, _sqlite

_SQLITE = """
CREATE TABLE IF NOT EXISTS runtime_settings (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
)
"""

_POSTGRES = """
CREATE TABLE IF NOT EXISTS runtime_settings (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
)
"""


def _preparar(conn, postgres: bool) -> None:
    if postgres:
        with conn.cursor() as cur:
            cur.execute(_POSTGRES)
    else:
        conn.execute(_SQLITE)


def get(chave: str) -> str | None:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn:
            _preparar(conn, True)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT valor FROM runtime_settings WHERE chave = %s", (chave,)
                )
                linha = cur.fetchone()
        return linha[0] if linha else None
    with _sqlite() as conn:
        _preparar(conn, False)
        linha = conn.execute(
            "SELECT valor FROM runtime_settings WHERE chave = ?", (chave,)
        ).fetchone()
    return linha["valor"] if linha else None


def set(chave: str, valor: str) -> None:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn:
            _preparar(conn, True)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO runtime_settings (chave, valor) VALUES (%s, %s)
                    ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor
                    """,
                    (chave, valor),
                )
        return
    with _sqlite() as conn:
        _preparar(conn, False)
        conn.execute(
            """
            INSERT INTO runtime_settings (chave, valor) VALUES (?, ?)
            ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor
            """,
            (chave, valor),
        )
