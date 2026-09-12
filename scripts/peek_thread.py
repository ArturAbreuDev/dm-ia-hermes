"""Mostra o fim de uma conversa: perfil, lead e mensagens."""

from __future__ import annotations

import sys

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://dm-ia-hermes.vercel.app"

for igsid in sys.argv[1:]:
    resposta = httpx.get(
        f"{BASE}/v1/report/thread/{igsid}",
        params={"k": get_settings().diary_password, "limit": 12},
        timeout=120,
    )
    dados = resposta.json()
    print(f"\n===== {igsid}  perfil={dados.get('perfil')}  lead={dados.get('lead')}")
    for msg in dados.get("mensagens") or []:
        texto = (msg["text"] or "").replace("\n", " ")[:150]
        print(f"  {msg['role']:9} {texto}")
