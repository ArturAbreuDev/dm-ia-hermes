"""Cobra no Instagram quem gerou PIX no bot da Straton e não pagou."""

from __future__ import annotations

import logging
import unicodedata
from typing import Any

from app.store import memory

logger = logging.getLogger(__name__)

_IGNORAR = {"teste", "test", "aaaaa", "artur"}

_TEXTO = {
    "pending": (
        "amor, o pix já tá gerado aí no telegram. "
        "finaliza agora que você cai no grupo na hora 🔥"
    ),
    "expired": (
        "amor, aquele pix caiu. entra de novo no bot, gera outro e paga — "
        "é rápido e você já cai no grupo"
    ),
}


def _normaliza(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())


def match_igsid(buyer_name: str) -> str | None:
    """Só devolve IGSID se o nome bater em uma pessoa só."""
    nome = _normaliza(buyer_name)
    if len(nome) < 3:
        return None
    partes = nome.split()
    primeiro = partes[0]
    if primeiro in _IGNORAR:
        return None
    melhores: list[tuple[int, str]] = []
    for igsid, lead in memory.all_leads().items():
        if not igsid or igsid.startswith(("teste", "sim-", "prod-teste", "straton:")):
            continue
        if lead.get("paid") or lead.get("muted"):
            continue
        blob = _normaliza(f"{lead.get('name') or ''} {lead.get('username') or ''}")
        if not blob.strip():
            continue
        score = 0
        if nome == blob or (len(partes) > 1 and nome in blob):
            score = 3
        elif primeiro and (
            blob.split()[:1] == [primeiro]
            or (lead.get("username") or "").lower().startswith(primeiro)
        ):
            score = 2 if len(partes) > 1 and partes[1] in blob else 1
        if score:
            melhores.append((score, igsid))
    if not melhores:
        return None
    teto = max(s for s, _ in melhores)
    iguais = [i for s, i in melhores if s == teto]
    if len(iguais) != 1:
        return None
    return iguais[0]


def nudge(buyer_name: str, transaction_id: str, status: str) -> dict[str, Any]:
    """Manda DM se achar o lead. Não levanta erro pra quem chamou."""
    chave = f"straton:nudge:{transaction_id}:{status}"
    if memory.get_lead(chave).get("done"):
        return {"ok": False, "motivo": "ja_enviado"}
    igsid = match_igsid(buyer_name)
    if not igsid:
        return {"ok": False, "motivo": "sem_match"}
    texto = _TEXTO.get(status) or _TEXTO["pending"]
    try:
        from app.services.instagram import send_text_message

        send_text_message(igsid, texto)
        memory.save_message(igsid, "assistant", texto)
    except Exception as erro:  # noqa: BLE001
        logger.info("Nudge PIX falhou IGSID=%s: %s", igsid, erro)
        return {"ok": False, "motivo": "envio", "igsid": igsid, "erro": str(erro)[:200]}
    memory.save_lead(chave, {"done": True, "igsid": igsid})
    memory.set_lead_flag(igsid, f"pix_nudge_{status}", True)
    logger.info("Nudge PIX %s para IGSID=%s buyer=%s", status, igsid, buyer_name)
    return {"ok": True, "igsid": igsid, "status": status}
