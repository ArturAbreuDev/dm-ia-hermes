"""Resumo somente-leitura do movimento por dia (fuso de São Paulo)."""

from __future__ import annotations

import json
import sys

from app.store import memory

sys.stdout.reconfigure(encoding="utf-8")

TZ = "America/Sao_Paulo"
dsn = memory._postgres_dsn()
if not dsn:
    print("Sem DATABASE_URL no ambiente local: só há SQLite aqui, sem os dados de produção.")
    raise SystemExit(1)


def consultar(cur, sql: str, params: tuple = ()) -> list[tuple]:
    cur.execute(sql, params)
    return cur.fetchall()


with memory._postgres(dsn) as conn, conn.cursor() as cur:
    print("=== mensagens por dia (últimos 5 dias) ===")
    for dia, papel, qtd, pessoas in consultar(
        cur,
        f"""
        SELECT (created_at AT TIME ZONE %s)::date AS dia, role,
               COUNT(*), COUNT(DISTINCT sender_id)
          FROM messages
         WHERE created_at > now() - interval '5 days'
         GROUP BY dia, role
         ORDER BY dia DESC, role
        """,
        (TZ,),
    ):
        print(f"  {dia}  {papel:9} {qtd:5} msgs   {pessoas:3} pessoas")

    print("\n=== conversas novas por dia (primeira mensagem de cada pessoa) ===")
    for dia, qtd in consultar(
        cur,
        f"""
        SELECT (primeira AT TIME ZONE %s)::date AS dia, COUNT(*)
          FROM (SELECT sender_id, MIN(created_at) AS primeira
                  FROM messages GROUP BY sender_id) t
         WHERE primeira > now() - interval '5 days'
         GROUP BY dia ORDER BY dia DESC
        """,
        (TZ,),
    ):
        print(f"  {dia}  {qtd} conversas novas")

    print("\n=== volume por pessoa nas últimas 30h ===")
    for sender, entrada, saida, ultima in consultar(
        cur,
        f"""
        SELECT sender_id,
               COUNT(*) FILTER (WHERE role = 'user'),
               COUNT(*) FILTER (WHERE role = 'assistant'),
               MAX(created_at) AT TIME ZONE %s
          FROM messages
         WHERE created_at > now() - interval '30 hours'
         GROUP BY sender_id ORDER BY MAX(created_at) DESC
        """,
        (TZ,),
    ):
        print(f"  {sender:18} recebi={entrada:3} mandei={saida:3}  última {ultima:%d/%m %H:%M}")

    print("\n=== leads ===")
    linhas = consultar(
        cur,
        f"SELECT sender_id, data, updated_at AT TIME ZONE %s FROM leads ORDER BY updated_at DESC",
        (TZ,),
    )
    print(f"  {len(linhas)} leads no total")
    for sender, dados, atualizado in linhas:
        d = dados if isinstance(dados, dict) else json.loads(dados)
        marcas = [c for c, v in sorted(d.items()) if v is True]
        numeros = {c: v for c, v in sorted(d.items()) if isinstance(v, (int, float)) and v}
        print(f"  {sender:18} {atualizado:%d/%m %H:%M}  {marcas}  {numeros or ''}")
