from __future__ import annotations

import logging
import random
import time

from app.config import get_settings
from app.services import canned
from app.services.instagram import (
    send_audio_message,
    send_sender_action,
    send_text_message,
)
from app.store import memory
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(include_in_schema=False)


def _convites() -> tuple[str, ...]:
    preco = get_settings().active_price()
    if get_settings().checkout_provider() == "botgram":
        return (
            "te mando o link e você escolhe por lá 😏",
            f"olha, é {preco}, escolhe aí 👀",
            "deixa eu te mandar aqui, você escolhe o plano por lá 😏",
        )
    return (
        "te mando o link e você resolve por lá 😏",
        f"olha, é {preco}, entra aí 👀",
        "deixa eu te mandar aqui 😏",
    )


class OutreachRequest(BaseModel):
    igsids: list[str]
    text: str | None = None
    audio: bool = True


@router.post("/v1/outreach/flow")
def outreach_flow(payload: OutreachRequest, k: str | None = None) -> dict:
    """Manda o link e o áudio do fluxo para uma lista de contatos.

    Registra no lead como se tivesse saído na conversa normal, para o bot não
    repetir o mesmo áudio nem tratar essa pessoa como quem nunca viu o link.
    """
    settings = get_settings()
    if not settings.admin_key:
        raise HTTPException(status_code=503, detail="DIARY_PASSWORD não configurada")
    if k != settings.admin_key:
        raise HTTPException(status_code=403, detail="Chave inválida")
    link = settings.active_checkout_url()
    if not link:
        raise HTTPException(status_code=400, detail="Checkout não configurado")

    url_audio = canned.url_for(canned.GERAL) if payload.audio else None
    resultados = []

    for igsid in payload.igsids:
        item: dict = {"igsid": igsid}
        convite = payload.text or random.choice(_convites())
        mensagem = f"{convite} {link}"
        try:
            enviado = send_text_message(igsid, mensagem) or {}
            memory.save_message(igsid, "assistant", mensagem, mid=enviado.get("message_id"))
            memory.mark_link_sent(igsid)
            item["texto"] = "enviado"
        except Exception as erro:
            item["texto"] = f"falhou: {erro}"
            resultados.append(item)
            continue

        if url_audio:
            try:
                send_sender_action(igsid, "typing_on")
                time.sleep(2.0)
                send_audio_message(igsid, url_audio)
                memory.set_lead_flag(igsid, canned.GERAL.campo, True)
                item["audio"] = "enviado"
            except Exception as erro:
                item["audio"] = f"falhou: {erro}"
            finally:
                send_sender_action(igsid, "typing_off")

        resultados.append(item)
        logger.info("Disparo de fluxo para IGSID=%s: %s", igsid, item)

    return {"audio_url": url_audio, "resultados": resultados}
