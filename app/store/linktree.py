"""Botões do linktree — editáveis no site, sem redeploy."""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.store import runtime

CHAVE = "linktree"


def padrao() -> dict[str, Any]:
    bot = get_settings().telegram_vip_bot()
    return {
        "tagline": "Descobriu meu segredinho 😉",
        "instagram": (get_settings().instagram_handle or "").strip().lstrip("@"),
        "botoes": [
            {
                "titulo": "CANAL VIP 🔥",
                "desc": "Fotos e vídeos sem censura 🔥",
                "url": f"https://t.me/{bot}",
                "kind": "tg",
            },
            {
                "titulo": "Telegram PRÉVIAS 🌸",
                "desc": "Canal de prévias 🔥",
                "url": (get_settings().telegram_previews_url or "").strip(),
                "kind": "foto",
            },
        ],
    }


def _limpo_botao(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    titulo = str(item.get("titulo") or "").strip()[:80]
    url = str(item.get("url") or "").strip()[:500]
    if not titulo:
        return None
    kind = str(item.get("kind") or "foto").strip().lower()
    if kind not in {"tg", "foto", "privacy", "ig"}:
        kind = "foto"
    return {
        "titulo": titulo,
        "desc": str(item.get("desc") or "").strip()[:120],
        "url": url,
        "kind": kind,
    }


def carregar() -> dict[str, Any]:
    base = padrao()
    bruto = runtime.get(CHAVE)
    if not bruto:
        return base
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError:
        return base
    if not isinstance(dados, dict):
        return base
    tagline = str(dados.get("tagline") or base["tagline"]).strip()[:120]
    instagram = str(dados.get("instagram") or "").strip().lstrip("@")[:64]
    botoes = []
    for item in dados.get("botoes") or []:
        limpo = _limpo_botao(item)
        if limpo:
            botoes.append(limpo)
    if not botoes:
        botoes = base["botoes"]
    return {"tagline": tagline or base["tagline"], "instagram": instagram, "botoes": botoes}


def salvar(*, tagline: str, instagram: str, botoes: list[dict[str, str]]) -> dict[str, Any]:
    limpos = []
    for item in botoes:
        limpo = _limpo_botao(item)
        if limpo:
            limpos.append(limpo)
    dados = {
        "tagline": (tagline or "").strip()[:120] or padrao()["tagline"],
        "instagram": (instagram or "").strip().lstrip("@")[:64],
        "botoes": limpos or padrao()["botoes"],
    }
    runtime.set(CHAVE, json.dumps(dados, ensure_ascii=False))
    return dados
