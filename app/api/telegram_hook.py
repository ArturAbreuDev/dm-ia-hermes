from __future__ import annotations

import hmac
import logging
from typing import Any

from app.config import get_settings
from app.store import telegram_members
from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Telegram"])


@router.post("/webhooks/telegram")
async def receive_telegram_update(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> dict[str, Any]:
    """Registra quem entra e sai do grupo de compradores.

    Estar no grupo é prova de compra, mas a Bot API não deixa listar membros.
    Então guardamos cada entrada aqui, na hora que ela acontece.
    """
    settings = get_settings()
    segredo = settings.telegram_webhook_secret
    if not segredo:
        logger.error("TELEGRAM_WEBHOOK_SECRET não configurado; recusando o update")
        raise HTTPException(status_code=403, detail="Webhook não configurado")
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, segredo
    ):
        raise HTTPException(status_code=403, detail="Token secreto inválido")

    update = await request.json()
    anotados = _registrar(update, settings.telegram_group_chat_id)
    return {"status": "ok", "registrados": anotados}


def _registrar(update: dict, grupo: str) -> int:
    quantos = 0

    mudanca = update.get("chat_member") or {}
    if mudanca and _do_grupo(mudanca.get("chat"), grupo):
        # O afetado é new_chat_member.user, não o "from": "from" é quem agiu.
        novo = mudanca.get("new_chat_member") or {}
        pessoa = novo.get("user") or {}
        if pessoa.get("id"):
            telegram_members.save(
                user_id=str(pessoa["id"]),
                status=novo.get("status") or "member",
                username=pessoa.get("username"),
                first_name=pessoa.get("first_name"),
            )
            quantos += 1
            logger.info(
                "Telegram: %s (@%s) agora está %s no grupo",
                pessoa.get("first_name"),
                pessoa.get("username"),
                novo.get("status"),
            )

    # Grupos pequenos ainda mandam a mensagem de serviço. A Telegram avisa que
    # ela vai sumir dos grupos grandes, então é só reforço, não fonte única.
    mensagem = update.get("message") or {}
    if _do_grupo(mensagem.get("chat"), grupo):
        for pessoa in mensagem.get("new_chat_members") or []:
            if pessoa.get("id") and not pessoa.get("is_bot"):
                telegram_members.save(
                    user_id=str(pessoa["id"]),
                    status="member",
                    username=pessoa.get("username"),
                    first_name=pessoa.get("first_name"),
                )
                quantos += 1
        saiu = mensagem.get("left_chat_member") or {}
        if saiu.get("id"):
            telegram_members.save(
                user_id=str(saiu["id"]),
                status="left",
                username=saiu.get("username"),
                first_name=saiu.get("first_name"),
            )
            quantos += 1

    eu = update.get("my_chat_member") or {}
    if eu:
        chat = eu.get("chat") or {}
        status = (eu.get("new_chat_member") or {}).get("status")
        logger.info(
            "Telegram: o bot agora está %s em %s (id %s)",
            status,
            chat.get("title"),
            chat.get("id"),
        )

    return quantos


def _do_grupo(chat: dict | None, grupo: str) -> bool:
    if not chat:
        return False
    if not grupo:
        # Sem grupo configurado aceitamos qualquer um, para descobrir o id.
        return chat.get("type") in {"group", "supergroup", "channel"}
    return str(chat.get("id")) == str(grupo)
