"""Sonda a API da StratonBot com a chave de sandbox para descobrir o que existe.

Uso a chave de teste de propósito: descobrir rotas mexendo em produção não vale
o risco. Só GET, nada que crie ou altere nada.
"""

from __future__ import annotations

import json
import os
import re
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://stratonbot.app"
CHAVE = os.environ.get("STRATON_TEST_KEY", "")
if not CHAVE:
    sys.exit("Defina STRATON_TEST_KEY antes de rodar")

cliente = httpx.Client(timeout=45, follow_redirects=True)

print("=== de onde o painel carrega o javascript ===")
html = cliente.get(f"{BASE}/api").text
for padrao in [r'src="([^"]+\.js[^"]*)"', r'href="([^"]+\.css[^"]*)"', r'src="([^"]+)"']:
    achados = sorted(set(re.findall(padrao, html)))[:12]
    if achados:
        print(f"  {padrao} -> {achados}")

print("\n=== formatos de autenticação em /api/v1/me ===")
CABECALHOS = {
    "Authorization: Bearer": {"Authorization": f"Bearer {CHAVE}"},
    "X-API-Key": {"X-API-Key": CHAVE},
    "Authorization cru": {"Authorization": CHAVE},
    "x-api-secret": {"x-api-secret": CHAVE},
}
for nome, cabecalho in CABECALHOS.items():
    try:
        r = cliente.get(f"{BASE}/api/v1/me", headers=cabecalho)
        print(f"  {nome:<22} HTTP {r.status_code}  {r.text[:160]!r}")
    except Exception as erro:  # noqa: BLE001
        print(f"  {nome:<22} erro {erro}")

print("\n=== varredura de rotas (só GET) ===")
ROTAS = [
    "/api/v1",
    "/api/v1/",
    "/api/v1/me",
    "/api/v1/account",
    "/api/v1/bots",
    "/api/v1/orders",
    "/api/v1/pedidos",
    "/api/v1/sales",
    "/api/v1/vendas",
    "/api/v1/plans",
    "/api/v1/planos",
    "/api/v1/products",
    "/api/v1/produtos",
    "/api/v1/checkouts",
    "/api/v1/customers",
    "/api/v1/clientes",
    "/api/v1/subscribers",
    "/api/v1/assinantes",
    "/api/v1/subscriptions",
    "/api/v1/payments",
    "/api/v1/transactions",
    "/api/v1/revenue",
    "/api/v1/receita",
    "/api/v1/metrics",
    "/api/v1/stats",
    "/api/v1/webhooks",
    "/api/v1/funnels",
    "/api/v1/funis",
    "/api/v1/leads",
    "/api/v1/messages",
    "/api/v1/docs",
    "/api/v1/openapi",
    "/api/v1/openapi.json",
    "/api/v1/schema",
    "/api/docs/v1",
    "/api/reference",
]
auth = {"Authorization": f"Bearer {CHAVE}"}
for rota in ROTAS:
    try:
        r = cliente.get(f"{BASE}{rota}", headers=auth)
    except Exception as erro:  # noqa: BLE001
        print(f"  {rota:<28} erro {erro}")
        continue
    if r.status_code == 404:
        continue
    corpo = r.text[:400]
    try:
        corpo = json.dumps(r.json(), ensure_ascii=False)[:400]
    except Exception:  # noqa: BLE001
        pass
    print(f"  {rota:<28} HTTP {r.status_code}  {corpo}")
