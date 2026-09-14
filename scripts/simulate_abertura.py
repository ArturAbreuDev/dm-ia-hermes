"""Confere em produção se o link novo já está saindo e como ela recebe uma
chegada ousada. Usa sender_id com prefixo sim-, que o relatório ignora."""

from __future__ import annotations

import sys
import uuid

import httpx

from app.config import get_settings
from app.services import tone

sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://dm-ia-hermes.vercel.app"
chave = get_settings().diary_password


def conversa(rotulo: str, falas: list[str]) -> None:
    sender = f"sim-{uuid.uuid4().hex[:8]}"
    print(f"\n=== {rotulo} ({sender}) ===")
    for fala in falas:
        r = httpx.post(
            f"{BASE}/v1/simulate",
            params={"k": chave},
            json={"sender_id": sender, "text": fala},
            timeout=180,
        )
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:200]}")
            return
        dados = r.json()
        dela = dados.get("reply") or ""
        print(f"  ele:  {fala!r}")
        for parte in tone.split_messages(dela) or ["(nao respondeu)"]:
            print(f"  ELA:  {parte}")
        print(f"        [{dados.get('intent')}]")


conversa("chegada ousada", ["vc é muito gostosa", "e depois disso?", "e ai"])
conversa(
    "pergunta como funciona e depois muda de assunto",
    ["oi", "como funciona?", "e vc gosta de que?", "responde ai"],
)
