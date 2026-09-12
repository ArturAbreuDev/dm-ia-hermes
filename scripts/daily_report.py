"""Busca o relatório de produção e imprime legível, com @ de cada pessoa."""

from __future__ import annotations

import sys

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://dm-ia-hermes.vercel.app"

resposta = httpx.get(
    f"{BASE}/v1/report",
    params={"k": get_settings().diary_password, "days": 7, "profiles": True},
    timeout=280,
)
resposta.raise_for_status()
dados = resposta.json()

print(f"gerado em {dados['gerado_em']}\n")

print("=== por dia (fuso SP) ===")
for dia, d in dados["dias"].items():
    print(
        f"  {dia}  recebidas={d['recebidas']:4}  enviadas={d['enviadas']:4}"
        f"  pessoas={d['pessoas']:3}  novas={d['novas']:3}"
    )

print("\n=== últimas 30h, por pessoa ===")
for sender, p in dados["ultimas_30h"].items():
    quem = p.get("username") or p.get("nome") or sender
    print(
        f"  @{quem:24} recebi={p['recebidas']:3} mandei={p['enviadas']:3}"
        f"  até {p['ultima']}  {p['marcas']} {p['numeros'] or ''}"
    )

print(f"\n=== leads === {dados['leads']}")
