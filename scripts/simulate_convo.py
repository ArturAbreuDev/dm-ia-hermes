"""Repete uma conversa contra a produção para ver o tom que sai.

Usa sender_id com prefixo sim-, que o relatório já ignora, para o teste não
sujar os números do dia.
"""

from __future__ import annotations

import sys
import uuid

import httpx

from app.config import get_settings
from app.services import tone

sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://dm-ia-hermes.vercel.app"

# A conversa do print com o Rafael, na ordem em que ele mandou.
FALAS = [
    "Oi",
    "Tudo e contigo ?",
    "Tá tudo também\nNada",
    "Normalmente tou a descansar nesse tempo 😂",
    "Não",
    "tem mais coisa?",
]

sender = f"sim-{uuid.uuid4().hex[:8]}"
chave = get_settings().diary_password
print(f"conversa de teste: {sender}\n")

perguntas = 0
for fala in FALAS:
    resposta = httpx.post(
        f"{BASE}/v1/simulate",
        params={"k": chave},
        json={"sender_id": sender, "text": fala},
        timeout=120,
    )
    if resposta.status_code != 200:
        print(f"  HTTP {resposta.status_code}: {resposta.text[:200]}")
        break
    dela = resposta.json().get("reply") or ""
    print(f"  ele:  {fala!r}")
    for parte in tone.split_messages(dela) or ["(sem resposta)"]:
        print(f"  ELA:  {parte}")
    if "?" in dela:
        perguntas += 1
    print()

print(f"{perguntas} de {len(FALAS)} respostas tinham pergunta")
