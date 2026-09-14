from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from app.config import get_settings
from app.services import (
    canned,
    engagement,
    incoming,
    payment,
    purchase,
    stories,
    timing,
    tone,
    voice,
)
from app.services.instagram import (
    get_user_profile,
    send_audio_message,
    send_sender_action,
    send_text_message,
)
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


def _handle_echo(event: dict[str, Any], message: dict[str, Any], settings) -> None:
    """Decide se a mensagem que saiu foi do bot ou da Lívia digitando na mão.

    No eco quem manda é a conta, então o contato está no recipient. Se a Lívia
    entrou na conversa, o bot sai de cena: ela assumiu, e duas vozes ao mesmo
    tempo estragam tudo.
    """
    mid = message.get("mid")
    # Nossos próprios envios são gravados com o mid que a API devolve.
    if memory.already_processed(mid):
        return

    contato = (event.get("recipient") or {}).get("id")
    proprios = {settings.instagram_id, settings.instagram_page_id, settings.instagram_user_id}
    if not contato or contato in proprios:
        return

    texto = (message.get("text") or "").strip()
    # Rede de segurança para o caso do eco chegar antes de gravarmos o mid.
    if texto and texto == (memory.last_assistant_text(contato) or "").strip():
        return

    memory.save_message(contato, "assistant", texto or "[mídia enviada à mão]", mid=mid)
    memory.mark_human_reply(contato)
    logger.info(
        "Resposta manual para IGSID=%s; bot em silêncio por %s min",
        contato,
        settings.human_takeover_minutes,
    )


def _enviar_em_partes(sender_id: str, reply: str) -> bool:
    """Manda a resposta como uma ou duas DMs curtas, com pausa entre elas.

    Cada parte é gravada com o mid que a API devolve. Sem isso o eco da segunda
    parte chegaria como desconhecido e o bot acharia que a Lívia respondeu à
    mão, calando a si mesmo por quinze minutos.
    """
    partes = tone.split_messages(reply)
    if not partes:
        return False

    for indice, parte in enumerate(partes):
        if indice:
            # Ninguém emenda duas mensagens no mesmo instante.
            send_sender_action(sender_id, "typing_on")
            time.sleep(min(len(parte) / 5.0 + 0.8, 4.0))
        try:
            enviado = send_text_message(sender_id, parte) or {}
        except httpx.HTTPStatusError as extra:
            # Conta apagada, desativada ou que bloqueou o perfil: não há o que fazer.
            logger.warning(
                "Não consegui entregar para IGSID=%s: %s", sender_id, extra.response.text
            )
            return indice > 0
        memory.save_message(sender_id, "assistant", parte, mid=enviado.get("message_id"))

    if len(partes) > 1:
        logger.info("Resposta para IGSID=%s saiu em %s mensagens", sender_id, len(partes))
    return True


def _handle_messaging_event(event: dict[str, Any]) -> None:
    message = event.get("message") or {}
    sender_id = (event.get("sender") or {}).get("id")
    print(
        "ig_webhook sender_id=%s echo=%s has_message=%s"
        % (sender_id, bool(message.get("is_echo")), bool(message)),
        flush=True,
    )
    if not sender_id or not message:
        logger.info("Ignorado: evento sem remetente ou sem mensagem")
        return
    settings = get_settings()

    # Eco: saiu mensagem desta conta. Pode ter sido o bot ou a Lívia na mão.
    if message.get("is_echo"):
        _handle_echo(event, message, settings)
        return

    for bandeira in ("is_deleted", "is_unsupported"):
        if message.get(bandeira):
            logger.info("Ignorado IGSID=%s: mensagem marcada como %s", sender_id, bandeira)
            return
    if sender_id in {settings.instagram_id, settings.instagram_page_id, settings.instagram_user_id}:
        logger.info("Ignorado: a mensagem é da própria conta")
        return

    mid = message.get("mid")
    if memory.already_processed(mid):
        logger.info("Ignorado IGSID=%s: mid %s já processado", sender_id, mid)
        return

    chegada = incoming.read(message)
    text = chegada.text
    incoming_is_audio = chegada.is_audio
    logger.info("Recebido IGSID=%s tipo=%s texto=%r", sender_id, chegada.kind, text[:160])

    memory.save_message(sender_id, "user", text, mid=mid)

    perfil = get_user_profile(sender_id)

    # Estar no grupo do Telegram é prova de compra; a palavra dele é só indício.
    if purchase.confirm_via_telegram(sender_id, perfil.get("username")):
        pass
    elif payment.claims_payment(text):
        if not memory.is_paid(sender_id):
            logger.info("IGSID=%s disse que pagou; encerrando a venda", sender_id)
        memory.mark_paid(sender_id)
    already_paid = memory.is_paid(sender_id)

    # A Lívia assumiu a conversa há pouco. O estado continua em dia, mas quem
    # fala é ela. Quando a janela vence sem mensagem nova, o bot volta sozinho.
    espera = memory.human_pause_seconds(sender_id)
    if espera > 0:
        logger.info(
            "Ignorado IGSID=%s: resposta manual recente, faltam %.0f min",
            sender_id,
            espera / 60,
        )
        return

    # Um só lugar decide se ainda vale a pena responder, e com que clima.
    lead = memory.get_lead(sender_id)
    stance = engagement.decide(lead, text, already_paid)
    if stance.mute and not lead.get("muted"):
        memory.set_muted(sender_id, True)
        logger.info("IGSID=%s silenciado de vez: %s", sender_id, stance.reason)
    if stance.silent:
        logger.info("Ignorado IGSID=%s: %s", sender_id, stance.reason)
        return
    logger.info(
        "Clima IGSID=%s motivo=%s sinais=%s despedida=%s",
        sender_id,
        stance.reason,
        sorted(stance.flags) or "-",
        stance.farewell.doing if stance.farewell else "-",
    )

    if wants_human(text):
        logger.info("Handoff pedido por IGSID=%s; nenhuma resposta automática", sender_id)
        return

    stories.maybe_sync()
    as_voice = voice.is_voice_moment(text, incoming_is_audio, sales_open=not already_paid)
    first_name = voice.first_speakable_name(perfil)

    result = generate_sales_reply(
        sender_id,
        text,
        first_name=first_name,
        as_voice=as_voice,
        story_reply=chegada.story_reply,
        must_reply=chegada.is_media and not already_paid,
        already_paid=already_paid,
        stance=stance,
    )
    if not result.should_send:
        logger.info(
            "Sem resposta para IGSID=%s intent=%s tipo=%s",
            sender_id,
            result.intent,
            chegada.kind,
        )
        return

    will_send_audio = voice.should_use_voice(
        text, result.reply, incoming_is_audio, sales_open=not already_paid
    )
    plan = timing.reply_plan(result.reply, is_hot=as_voice, as_voice=will_send_audio)
    logger.info(
        "Plano IGSID=%s silencio=%.1fs digitando=%.1fs audio=%s",
        sender_id,
        plan.silence,
        plan.typing,
        will_send_audio,
    )

    # Enquanto ela "não viu", a mensagem fica sem visualizar mesmo.
    if plan.silence:
        time.sleep(plan.silence)
    send_sender_action(sender_id, "mark_seen")

    # O áudio é gerado durante o "digitando", que é justamente o tempo que ela
    # levaria para gravar. Assim a espera não fica em cima da espera.
    if plan.typing:
        send_sender_action(sender_id, "typing_on")

    inicio = time.monotonic()
    audio_url = voice.build_audio_url(result.reply) if will_send_audio else None
    restante = plan.typing - (time.monotonic() - inicio)
    if restante > 0:
        time.sleep(restante)

    sent_as_audio = False
    enviado: dict[str, Any] = {}
    if audio_url:
        try:
            enviado = send_audio_message(sender_id, audio_url) or {}
            sent_as_audio = True
        except Exception:
            logger.exception("Falha ao enviar áudio; caindo para texto")

    if sent_as_audio:
        # Guardar o mid do nosso próprio envio é o que faz o eco dele ser
        # reconhecido depois, em vez de parecer que a Lívia respondeu à mão.
        memory.save_message(
            sender_id, "assistant", result.reply, mid=enviado.get("message_id")
        )
    elif not _enviar_em_partes(sender_id, result.reply):
        return

    send_sender_action(sender_id, "typing_off")
    for campo in stance.counters:
        memory.bump_lead_counter(sender_id, campo)
    if settings.checkout_url and settings.checkout_url in result.reply:
        memory.mark_link_sent(sender_id)

    # Explicar o fluxo é sempre a mesma explicação, e falada convence mais.
    # Vai depois do texto, como quem completa a ideia num áudio.
    if stance.abertura:
        pronto = canned.abertura(first_name)
    else:
        pronto = canned.pick(result.reply, stance.flags, lead)
    if pronto and not sent_as_audio:
        url_pronta = canned.url_for(pronto)
        if url_pronta:
            try:
                send_sender_action(sender_id, "typing_on")
                time.sleep(min(len(pronto.texto) / 14.0, 8.0))
                send_audio_message(sender_id, url_pronta)
                memory.set_lead_flag(sender_id, pronto.campo, True)
                logger.info("Áudio pronto %s enviado para IGSID=%s", pronto.nome, sender_id)
            except Exception:
                logger.exception("Falha ao enviar o áudio pronto %s", pronto.nome)
            finally:
                send_sender_action(sender_id, "typing_off")
    logger.info("Respondido IGSID=%s intent=%s audio=%s", sender_id, result.intent, sent_as_audio)
