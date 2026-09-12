"""Simula em produção o cara que só faz sala, elogia e depois pergunta como funciona.

Usa sender_id com prefixo sim-, que o relatório já ignora, para não sujar o dia.
"""

from __future__ import annotations

import sys
import uuid

import httpx

from app.config import get_settings
from app.services import tone

sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://dm-ia-hermes.vercel.app"

FALAS = [
    "Oi",
    "tudo bem?",
    "vc é muito linda sabia",
    "nossa que corpo",
    "você é perfeita mesmo",
    "amei seu perfil",
    "como funciona?",
]

sender = f"sim-{uuid.uuid4().hex[:8]}"
chave = get_settings().diary_password
link = get_settings().checkout_url
print(f"conversa de teste: {sender}\n")

for fala in FALAS:
    resposta = httpx.post(
        f"{BASE}/v1/simulate",
        params={"k": chave},
        json={"sender_id": sender, "text": fala},
        timeout=180,
    )
    if resposta.status_code != 200:
        print(f"  HTTP {resposta.status_code}: {resposta.text[:300]}")
        break
    dados = resposta.json()
    dela = dados.get("reply") or ""
    print(f"  ele:  {fala!r}")
    for parte in tone.split_messages(dela) or ["(nao respondeu)"]:
        print(f"  ELA:  {parte}")
    marcas = []
    if link and link in dela:
        marcas.append("LINK")
    if "?" in dela:
        marcas.append("pergunta")
    print(f"        [{dados.get('intent')}]{' ' + ' '.join(marcas) if marcas else ''}\n")
