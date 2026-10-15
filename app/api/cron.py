"""Recupera PIX pendente da Straton antes de expirar.

A venda cai porque o PIX fica ~30 min aberto e ninguém cobra. O webhook
`cashin.pending` avisa na hora; este cron é a rede de segurança quando o
webhook atrasa ou não está ligado no painel.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.services import alert, straton
from app.store import memory, runtime
from fastapi import APIRouter, Header, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(include_in_schema=False)


def _segredos() -> list[str]:
    settings = get_settings()
    vistos: list[str] = []
    for valor in (settings.cron_secret, settings.diary_password, settings.admin_key):
        v = (valor or "").strip()
        if v and v not in vistos:
            vistos.append(v)
    return vistos


def _autorizado(
    authorization: str | None,
    cron_secret_header: str | None,
    *,
    x_vercel_cron: str | None = None,
    k: str | None = None,
) -> bool:
    if (x_vercel_cron or "").strip() == "1":
        return True
    senhas = _segredos()
    if not senhas:
        return False
    if k and k in senhas:
        return True
    if cron_secret_header and cron_secret_header in senhas:
        return True
    if authorization:
        token = authorization.removeprefix("Bearer ").strip()
        if token in senhas:
            return True
    return False


@router.get("/v1/cron/straton-pending")
@router.post("/v1/cron/straton-pending")
def recuperar_pendentes(
    authorization: str | None = Header(default=None),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
    x_vercel_cron: str | None = Header(default=None, alias="x-vercel-cron"),
    k: str = Query(""),
) -> dict:
    """Varre PIX abertos e avisa. Idempotente por transaction_id."""
    if not _autorizado(authorization, x_cron_secret, x_vercel_cron=x_vercel_cron, k=k):
        raise HTTPException(status_code=403, detail="Cron não autorizado")

    settings = get_settings()
    if not settings.straton_api_key:
        return {"status": "sem_chave", "avisados": 0}

    pendentes = straton.pending_bot_sales(limit=50)
    avisados = 0
    for item in pendentes:
        tx = str(item.get("id") or "")
        if not tx:
            continue
        # Mesma chave que o webhook usa, pra não duplicar se os dois rodarem.
        if memory.get_lead(f"straton:pix_pendente:{tx}").get("avisado"):
            continue
        if alert.notify_pix_status(
            "pix_pendente",
            str(item.get("buyer_name") or ""),
            tx,
            item.get("amount_cents"),
            detalhe=f"criado em {item.get('created_at') or '?'}",
        ):
            avisados += 1
        from app.services import pix_rmk

        pix_rmk.nudge(str(item.get("buyer_name") or ""), tx, "pending")

    runtime.set("straton_last_pending_scan", str(len(pendentes)))
    logger.info(
        "Cron Straton: %s pendentes, %s avisos novos", len(pendentes), avisados
    )
    return {
        "status": "ok",
        "pendentes": len(pendentes),
        "avisados": avisados,
        "itens": [
            {
                "id": i.get("id"),
                "buyer": i.get("buyer_name"),
                "amount_cents": i.get("amount_cents"),
                "created_at": i.get("created_at"),
            }
            for i in pendentes
        ],
    }


@router.get("/v1/cron/publish-due")
@router.post("/v1/cron/publish-due")
def publicar_agendados(
    authorization: str | None = Header(default=None),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
    x_vercel_cron: str | None = Header(default=None, alias="x-vercel-cron"),
    k: str = Query(""),
) -> dict:
    """Publica posts/reels/stories cuja hora já chegou."""
    if not _autorizado(
        authorization, x_cron_secret, x_vercel_cron=x_vercel_cron, k=k
    ):
        raise HTTPException(status_code=403, detail="Cron não autorizado")
    from app.services import scheduler, telegram_sales

    publicado = scheduler.process_due()
    rmk = telegram_sales.process_due(limit=20)
    return {"publish": publicado, "rmk": rmk}


@router.get("/v1/cron/rmk")
@router.post("/v1/cron/rmk")
def disparar_rmk(
    authorization: str | None = Header(default=None),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
    x_vercel_cron: str | None = Header(default=None, alias="x-vercel-cron"),
    k: str = Query(""),
) -> dict:
    """Manda as mensagens de recorrência cuja hora já chegou."""
    if not _autorizado(
        authorization, x_cron_secret, x_vercel_cron=x_vercel_cron, k=k
    ):
        raise HTTPException(status_code=403, detail="Cron não autorizado")
    from app.services import telegram_sales

    return telegram_sales.process_due(limit=20)


@router.get("/v1/cron/previas-semana")
@router.post("/v1/cron/previas-semana")
def previa_semanal(
    authorization: str | None = Header(default=None),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
    x_vercel_cron: str | None = Header(default=None, alias="x-vercel-cron"),
    k: str = Query(""),
) -> dict:
    """Sobe uma prévia do RMK no grupo, uma vez por semana."""
    if not _autorizado(
        authorization, x_cron_secret, x_vercel_cron=x_vercel_cron, k=k
    ):
        raise HTTPException(status_code=403, detail="Cron não autorizado")
    from app.services import previews

    try:
        return previews.publicar_semanal()
    except Exception as erro:
        logger.exception("prévia semanal falhou")
        raise HTTPException(status_code=502, detail=str(erro)[:200]) from erro


@router.get("/v1/cron/ensure-jobs")
@router.post("/v1/cron/ensure-jobs")
def garantir_jobs(
    authorization: str | None = Header(default=None),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
    x_vercel_cron: str | None = Header(default=None, alias="x-vercel-cron"),
    k: str = Query(""),
) -> dict:
    """Cria/atualiza os crons no cron-job.org (RMK a cada 5 min)."""
    if not _autorizado(
        authorization, x_cron_secret, x_vercel_cron=x_vercel_cron, k=k
    ):
        raise HTTPException(status_code=403, detail="Cron não autorizado")
    from app.services import cronjobs, telegram

    try:
        telegram.ensure_webhook()
        return cronjobs.ensure()
    except Exception as erro:
        logger.exception("cron-job.org falhou")
        raise HTTPException(status_code=502, detail=str(erro)[:200]) from erro
