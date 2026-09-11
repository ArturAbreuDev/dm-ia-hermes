from __future__ import annotations

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
from app.services import telegram
from app.store import memory
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Hermes"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/simulate", response_model=SimulateResponse)
def simulate_reply(payload: SimulateRequest) -> SimulateResponse:
    """Gera uma resposta de venda sem chamar o Instagram. Útil para testar o agente."""
    memory.save_message(payload.sender_id, "user", payload.text)
    result = generate_sales_reply(payload.sender_id, payload.text)
    memory.save_message(payload.sender_id, "assistant", result.reply)
    if result.lead:
        memory.save_lead(payload.sender_id, result.lead)
    return SimulateResponse(reply=result.reply, handoff=result.handoff, intent=result.intent)


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

