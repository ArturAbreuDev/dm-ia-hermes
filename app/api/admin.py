from __future__ import annotations

import uuid
from typing import Any

from app.config import get_settings
from app.models.schemas import (
    HealthResponse,
    SendMessageRequest,
    SendMessageResponse,
    SimulateRequest,
    SimulateResponse,
    TelegramSendResponse,
    TelegramTextRequest,
    TelegramVoiceRequest,
)
from app.services.instagram import send_text_message
from app.services.sales_agent import generate_sales_reply
from app.services import canned, engagement, stories, telegram
from app.store import memory, story_context
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["Hermes"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


class StoryNoteRequest(BaseModel):
    text: str
    id: str | None = None


def _conferir_chave(chave: str | None) -> None:
    """Estas rotas silenciam conversas e marcam gente como paga: não podem ficar
    abertas na internet. A senha é a mesma do /diario, para não criar outra."""
    esperada = get_settings().admin_key
    if not esperada:
        raise HTTPException(status_code=503, detail="DIARY_PASSWORD não configurada")
    if chave != esperada:
        raise HTTPException(status_code=403, detail="Chave inválida")


@router.get("/leads/{igsid}")
def ver_lead(igsid: str, k: str | None = None) -> dict[str, Any]:
    _conferir_chave(k)
    return {"igsid": igsid, "lead": memory.get_lead(igsid)}


@router.post("/leads/{igsid}/mute")
def silenciar(igsid: str, k: str | None = None) -> dict[str, Any]:
    """Para de responder este contato, exceto se ele falar de comprar ou pagar."""
    _conferir_chave(k)
    memory.set_muted(igsid, True)
    return {"igsid": igsid, "lead": memory.get_lead(igsid)}


@router.delete("/leads/{igsid}/mute")
def dessilenciar(igsid: str, k: str | None = None) -> dict[str, Any]:
    _conferir_chave(k)
    memory.set_muted(igsid, False)
    return {"igsid": igsid, "lead": memory.get_lead(igsid)}


@router.post("/leads/{igsid}/paid")
def marcar_pago(igsid: str, k: str | None = None) -> dict[str, Any]:
    """Encerra a venda na mão, quando o pagamento foi confirmado por fora."""
    _conferir_chave(k)
    memory.mark_paid(igsid)
    return {"igsid": igsid, "lead": memory.get_lead(igsid)}


@router.delete("/leads/{igsid}/paid")
def desmarcar_pago(igsid: str, k: str | None = None) -> dict[str, Any]:
    """Desfaz, para o caso de falso positivo: alguém que disse ter pago e não pagou."""
    _conferir_chave(k)
    memory.clear_paid(igsid)
    return {"igsid": igsid, "lead": memory.get_lead(igsid)}


@router.get("/context")
def list_context() -> dict[str, Any]:
    """Mostra o que a Livia sabe da própria vida hoje."""
    return {"itens": story_context.recent(limit=20)}


@router.post("/context/notes")
def add_context_note(payload: StoryNoteRequest) -> dict[str, Any]:
    """Anota um acontecimento na mão, para quando não vier de um story.

    Serve para o que a API não entrega: story que já expirou, story postado na
    conta principal, ou qualquer coisa que ela deveria saber sobre si mesma.
    """
    texto = payload.text.strip()
    if not texto:
        raise HTTPException(status_code=400, detail="Texto vazio")
    entry_id = payload.id or f"nota-{uuid.uuid4().hex[:12]}"
    story_context.save(entry_id, texto, kind="nota")
    return {"id": entry_id, "description": texto}


@router.post("/context/sync-stories")
def sync_stories() -> dict[str, Any]:
    """Lê os stories ativos da conta conectada e descreve os novos."""
    descritos = stories.sync_active_stories()
    return {"descritos": descritos, "total": len(descritos)}


@router.post("/simulate", response_model=SimulateResponse)
def simulate_reply(payload: SimulateRequest) -> SimulateResponse:
    """Gera uma resposta de venda sem chamar o Instagram. Útil para testar o agente.

    O clima e os contadores são os mesmos do webhook de propósito. Sem isso o
    simulador não veria nada do que depende de sinal — mandar o link no "como
    funciona", esfriar com quem só faz sala, calar quem passou do teto — e
    testar aqui devolveria uma resposta que a produção não daria.
    """
    lead = memory.get_lead(payload.sender_id)
    pago = memory.is_paid(payload.sender_id)
    stance = engagement.decide(lead, payload.text, pago)
    memory.save_message(payload.sender_id, "user", payload.text)
    if stance.silent:
        return SimulateResponse(reply="", intent=f"calado:{stance.reason}")

    result = generate_sales_reply(
        payload.sender_id, payload.text, stance=stance, already_paid=pago
    )
    memory.save_message(payload.sender_id, "assistant", result.reply)
    if result.lead:
        memory.save_lead(payload.sender_id, result.lead)
    for campo in stance.counters:
        memory.bump_lead_counter(payload.sender_id, campo)
    settings = get_settings()
    if settings.checkout_url and settings.checkout_url in result.reply:
        memory.mark_link_sent(payload.sender_id)

    pronto = canned.pick(result.reply, stance.flags, lead)
    intent = result.intent or "chat"
    if pronto:
        # Só o nome: gerar o áudio de novo custaria à toa num teste.
        intent = f"{intent}+audio:{pronto.nome}"
        memory.set_lead_flag(payload.sender_id, pronto.campo, True)
    return SimulateResponse(reply=result.reply, handoff=result.handoff, intent=intent)


@router.post("/messages", response_model=SendMessageResponse)
def send_message(payload: SendMessageRequest) -> SendMessageResponse:
    """Envia um DM manual pela Instagram Messaging API."""
    settings = get_settings()
    if not settings.instagram_access_token or not settings.instagram_id:
        raise HTTPException(status_code=400, detail="Instagram ainda não está configurado no .env")
    response = send_text_message(payload.recipient_id, payload.text)
    return SendMessageResponse(recipient_id=payload.recipient_id, message_id=response.get("message_id"))


def _resolve_telegram_chat_id(chat_id: str | None, to: str | None) -> str:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="Telegram ainda não está configurado no .env")
    if chat_id:
        return chat_id
    if to:
        found = telegram.find_chat_id(to)
        if found is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Não achei '{to}' no Telegram. Abra t.me/liviagommes_bot, toque em Start "
                    "e mande qualquer mensagem; depois tente de novo."
                ),
            )
        return str(found)
    if settings.telegram_default_chat_id:
        return settings.telegram_default_chat_id
    raise HTTPException(status_code=400, detail="Informe chat_id, to, ou TELEGRAM_DEFAULT_CHAT_ID")


@router.post("/telegram/messages", response_model=TelegramSendResponse)
def send_telegram_text(payload: TelegramTextRequest) -> TelegramSendResponse:
    """Envia um texto pelo bot do Telegram."""
    chat_id = _resolve_telegram_chat_id(payload.chat_id, payload.to)
    result = telegram.send_text_message(chat_id, payload.text)
    return TelegramSendResponse(chat_id=str(chat_id), message_id=result.get("message_id"))


@router.post("/telegram/voice", response_model=TelegramSendResponse)
def send_telegram_voice(payload: TelegramVoiceRequest) -> TelegramSendResponse:
    """Envia um áudio como voice message (OGG/Opus) pelo Telegram."""
    chat_id = _resolve_telegram_chat_id(payload.chat_id, payload.to)
    try:
        result = telegram.send_voice_message(chat_id, payload.audio_path, caption=payload.caption)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TelegramSendResponse(chat_id=str(chat_id), message_id=result.get("message_id"))

