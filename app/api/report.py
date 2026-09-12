from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.services.instagram import get_user_profile
from app.store import memory
from fastapi import APIRouter, HTTPException

router = APIRouter(include_in_schema=False)

FUSO = ZoneInfo("America/Sao_Paulo")


def _lixo(sender_id: str) -> bool:
    """Fora da contagem: os testes e a conversa fantasma que o echo criou debaixo
    do próprio ID da conta antes da correção do webhook."""
    settings = get_settings()
    proprios = {settings.instagram_id, settings.instagram_page_id, settings.instagram_user_id}
    return sender_id in proprios or sender_id.startswith(("teste", "prod-teste", "sim-"))


def _dia(momento: datetime) -> str:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(FUSO).date().isoformat()


@router.get("/v1/report/thread/{igsid}")
def thread(igsid: str, k: str | None = None, limit: int = 40) -> dict:
    """Últimas mensagens de uma conversa, para conferir caso estranho."""
    settings = get_settings()
    if not settings.admin_key or k != settings.admin_key:
        raise HTTPException(status_code=403, detail="Chave inválida")
    return {
        "igsid": igsid,
        "perfil": get_user_profile(igsid),
        "lead": memory.get_lead(igsid),
        "mensagens": memory.get_history(igsid, limit=limit),
    }


@router.get("/v1/report")
def report(k: str | None = None, days: int = 7, profiles: bool = False) -> dict:
    """Agregados de conversa por dia, no fuso de São Paulo."""
    settings = get_settings()
    if not settings.admin_key:
        raise HTTPException(status_code=503, detail="DIARY_PASSWORD não configurada")
    if k != settings.admin_key:
        raise HTTPException(status_code=403, detail="Chave inválida")

    mensagens = [m for m in memory.message_activity(days=days) if not _lixo(m["sender_id"])]
    leads = {s: d for s, d in memory.all_leads().items() if not _lixo(s)}
    primeira_vez = {s: q for s, q in memory.first_seen().items() if not _lixo(s)}

    por_dia: dict[str, dict] = defaultdict(
        lambda: {"recebidas": 0, "enviadas": 0, "pessoas": set(), "novas": 0}
    )
    for msg in mensagens:
        dia = por_dia[_dia(msg["created_at"])]
        dia["recebidas" if msg["role"] == "user" else "enviadas"] += 1
        dia["pessoas"].add(msg["sender_id"])
    for sender, momento in primeira_vez.items():
        dia = _dia(momento)
        if dia in por_dia:
            por_dia[dia]["novas"] += 1

    corte = datetime.now(timezone.utc) - timedelta(hours=30)
    por_pessoa: dict[str, dict] = defaultdict(
        lambda: {"recebidas": 0, "enviadas": 0, "ultima": None}
    )
    for msg in mensagens:
        momento = msg["created_at"]
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=timezone.utc)
        if momento < corte:
            continue
        pessoa = por_pessoa[msg["sender_id"]]
        pessoa["recebidas" if msg["role"] == "user" else "enviadas"] += 1
        pessoa["ultima"] = momento.astimezone(FUSO).isoformat(timespec="minutes")

    for sender, pessoa in por_pessoa.items():
        lead = leads.get(sender, {})
        pessoa["marcas"] = sorted(c for c, v in lead.items() if v is True)
        pessoa["numeros"] = {c: v for c, v in sorted(lead.items()) if isinstance(v, int) and v}
        if profiles:
            perfil = get_user_profile(sender)
            pessoa["username"] = perfil.get("username")
            pessoa["nome"] = perfil.get("name")

    return {
        "gerado_em": datetime.now(FUSO).isoformat(timespec="seconds"),
        "dias": {
            dia: {**dados, "pessoas": len(dados["pessoas"])}
            for dia, dados in sorted(por_dia.items(), reverse=True)
        },
        "ultimas_30h": dict(
            sorted(por_pessoa.items(), key=lambda kv: kv[1]["ultima"] or "", reverse=True)
        ),
        "leads": {
            "total": len(leads),
            "pagos": sum(1 for d in leads.values() if d.get("paid")),
            "link_enviado": sum(1 for d in leads.values() if d.get("link_sent")),
            "silenciados": sum(1 for d in leads.values() if d.get("muted")),
        },
    }
