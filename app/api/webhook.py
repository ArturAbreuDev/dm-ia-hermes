from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from app.config import get_settings
from app.services import voice
from app.services.instagram import get_user_profile, send_audio_message, send_text_message
from app.services.sales_agent import generate_sales_reply, wants_human
from app.store import memory
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Instagram Webhook"])


@router.get("")
@router.get("/")
def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> Response:
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.verify_token and hub_challenge:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Falha na verificação do webhook")


@router.post("")
@router.post("/")
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict[str, str]:
    raw_body = await request.body()
    if not _valid_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as extra:
        raise HTTPException(status_code=400, detail="JSON inválido") from extra

    # Na Vercel o background task pode morrer ao responder; processa na hora.
    process_instagram_event(payload)
    return {"status": "accepted"}


def _valid_signature(raw_body: bytes, header: str | None) -> bool:
    settings = get_settings()
    if not settings.meta_app_secret:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.meta_app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    received = header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


def process_instagram_event(payload: dict[str, Any]) -> None:
    try:
        print(
            "ig_webhook object=%s entries=%s"
            % (payload.get("object"), len(payload.get("entry") or [])),
            flush=True,
        )
        if payload.get("object") not in {"instagram", "page"}:
            return
        for entry in payload.get("entry", []):
            events = entry.get("messaging") or []
            if not events and entry.get("changes"):
                for change in entry.get("changes", []):
                    value = change.get("value") or {}
                    if value.get("sender") or value.get("message"):
                        events.append(value)
            print("ig_webhook messaging_events=%s" % len(events), flush=True)
            for event in events:
                _handle_messaging_event(event)
    except Exception:
        logger.exception("Falha ao processar evento do Instagram")


def _handle_messaging_event(event: dict[str, Any]) -> None:
    message = event.get("message") or {}
    sender_id = (event.get("sender") or {}).get("id")
    print(
        "ig_webhook sender_id=%s echo=%s has_message=%s"
        % (sender_id, bool(message.get("is_echo")), bool(message)),
        flush=True,
    )
    if not sender_id or not message:
        return
    if message.get("is_echo") or message.get("is_deleted") or message.get("is_unsupported"):
        return
    settings = get_settings()
    if sender_id in {settings.instagram_id, settings.instagram_page_id, settings.instagram_user_id}:
        return

    mid = message.get("mid")
    if memory.already_processed(mid):
        return

    attachment_types = {
        (item or {}).get("type") for item in (message.get("attachments") or [])
    }
    incoming_is_audio = "audio" in attachment_types

    text = (message.get("text") or "").strip()
    if not text:
        if incoming_is_audio:
            text = "[a pessoa mandou um áudio]"
        else:
            text = "[mensagem sem texto: mídia, sticker ou compartilhamento]"

    memory.save_message(sender_id, "user", text, mid=mid)

    if wants_human(text):
        logger.info("Handoff pedido por IGSID=%s; nenhuma resposta automática", sender_id)
        return

    as_voice = voice.is_voice_moment(text, incoming_is_audio)
    first_name = voice.first_speakable_name(get_user_profile(sender_id))

    result = generate_sales_reply(
        sender_id, text, first_name=first_name, as_voice=as_voice
    )
    if not result.should_send:
        print("ig_webhook no_reply sender_id=%s" % sender_id, flush=True)
        return

    sent_as_audio = False
    if voice.should_use_voice(text, result.reply, incoming_is_audio):
        audio_url = voice.build_audio_url(result.reply)
        if audio_url:
            try:
                send_audio_message(sender_id, audio_url)
                sent_as_audio = True
            except Exception:
                logger.exception("Falha ao enviar áudio; caindo para texto")

    if not sent_as_audio:
        send_text_message(sender_id, result.reply)

    memory.save_message(sender_id, "assistant", result.reply)
    logger.info("Respondido IGSID=%s intent=%s audio=%s", sender_id, result.intent, sent_as_audio)
