from __future__ import annotations

import hmac
import logging
from typing import Any

from app.config import get_settings
from app.services import previews, telegram_sales
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
    canal = (update.get("channel_post") or {}).get("chat") or {}
    eu = (update.get("my_chat_member") or {}).get("chat") or {}
    priv = (update.get("message") or {}).get("chat") or {}
    print(
        "tg_upd",
        update.get("update_id"),
        "ch",
        canal.get("id"),
        canal.get("title"),
        canal.get("type"),
        "me",
        eu.get("id"),
        eu.get("title"),
        "priv",
        priv.get("type"),
        priv.get("id"),
        flush=True,
    )
    try:
        telegram_sales.process_due(limit=3)
    except Exception:
        logger.exception("RMK Telegram falhou no webhook")
    _ligar_previas(update)
    anotados = _registrar(update, settings.telegram_group_chat_id)
    privados = _atender_privado(update)
    return {"status": "ok", "registrados": anotados, "privado": privados}


def _ligar_previas(update: dict) -> None:
    """Descobre o grupo «livia porevias» sem misturar com VIP ou chat pessoal."""
    ligou = False
    eu = update.get("my_chat_member") or {}
    if eu:
        novo = eu.get("new_chat_member") or {}
        ligou = previews.lembrar(eu.get("chat"), status_bot=novo.get("status")) or ligou
        logger.info(
            "Telegram previas my_chat_member: %s %s id=%s",
            (eu.get("chat") or {}).get("title"),
            novo.get("status"),
            (eu.get("chat") or {}).get("id"),
        )
    mensagem = update.get("message") or {}
    if mensagem.get("chat"):
        ligou = previews.lembrar(mensagem.get("chat")) or ligou
    canal = update.get("channel_post") or {}
    if canal.get("chat"):
        logger.info(
            "Telegram previas channel_post: %s id=%s",
            (canal.get("chat") or {}).get("title"),
            (canal.get("chat") or {}).get("id"),
        )
        ligou = previews.lembrar(canal.get("chat")) or ligou
    if ligou:
        try:
            previews.publicar_do_funil()
        except Exception:
            logger.exception("dump das prévias na ligação falhou")


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
            if (novo.get("status") or "member") in telegram_members.DENTRO:
                telegram_sales.on_joined_group(str(pessoa["id"]))
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
                telegram_sales.on_joined_group(str(pessoa["id"]))
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


def _atender_privado(update: dict) -> str | None:
    query = update.get("callback_query")
    if query:
        chat = ((query.get("message") or {}).get("chat") or {})
        if chat.get("type") == "private" or not chat:
            try:
                return telegram_sales.handle_callback(query)
            except Exception:
                logger.exception("Callback do Telegram falhou")
                return "erro"
    mensagem = update.get("message") or {}
    if (mensagem.get("chat") or {}).get("type") != "private":
        return None
    dono = telegram_sales.eh_dono((mensagem.get("from") or {}).get("id"))
    if previews.chats_de_encaminhamento(mensagem):
        try:
            if previews.capturar_encaminhamento(mensagem, dono=dono):
                from app.services import telegram

                cid = (mensagem.get("chat") or {}).get("id")
                if cid:
                    telegram.send_text_message(
                        cid,
                        "Liguei o canal de prévias e mandei o conteúdo lá (não aqui no bot).",
                    )
                return "previas"
        except Exception:
            logger.exception("encaminhamento de prévias falhou")
            return "erro"
    if dono and not previews.chat_id():
        from app.services import telegram

        cid = (mensagem.get("chat") or {}).get("id")
        if cid:
            telegram.send_text_message(
                cid,
                "O número da URL do Telegram Web não é o id da API, então não "
                "acho o canal assim. Encaminha pra cá um post do "
                "«Livia Gomes - Previas» (o oi serve). Eu pego o id certo e "
                "publico LÁ, não aqui.",
            )
        return "previas-dica"
    try:
        return telegram_sales.handle_private_message(mensagem)
    except Exception:
        logger.exception("Mensagem privada do Telegram falhou")
        return "erro"


def _do_grupo(chat: dict | None, grupo: str) -> bool:
    if not chat:
        return False
    # Prévias nunca conta como comprador VIP.
    if previews.mesmo(chat.get("id")) or previews.titulo_de_previas(chat.get("title")):
        return False
    if not grupo:
        # Sem grupo configurado aceitamos qualquer um, para descobrir o id.
        return chat.get("type") in {"group", "supergroup", "channel"}
    return str(chat.get("id")) == str(grupo)
