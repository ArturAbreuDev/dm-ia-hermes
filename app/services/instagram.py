from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_text_message(recipient_id: str, text: str) -> dict[str, Any]:
    return _send(recipient_id, {"text": text[:1000]})


def send_audio_message(recipient_id: str, audio_url: str) -> dict[str, Any]:
    """Envia um áudio. O Instagram baixa o arquivo da URL informada."""
    return _send(
        recipient_id,
        {"attachment": {"type": "audio", "payload": {"url": audio_url}}},
    )


def send_sender_action(recipient_id: str, action: str) -> None:
    """Mostra os indicadores nativos da DM: visualizado e "digitando...".

    Falhar aqui não pode impedir a mensagem de sair, então só registramos o erro.
    """
    settings = get_settings()
    if not settings.instagram_access_token or not settings.instagram_id:
        return

    try:
        with httpx.Client(timeout=15) as client:
            response = client.post(
                settings.graph_messages_url,
                params={"access_token": settings.instagram_access_token},
                headers={
                    "Authorization": f"Bearer {settings.instagram_access_token}",
                    "Content-Type": "application/json",
                },
                json={"recipient": {"id": recipient_id}, "sender_action": action},
            )
            response.raise_for_status()
    except httpx.HTTPError as extra:
        detail = getattr(getattr(extra, "response", None), "text", extra)
        logger.warning("sender_action %s falhou: %s", action, detail)


def get_user_profile(igsid: str) -> dict[str, Any]:
    """Busca nome e @ de quem mandou a DM."""
    settings = get_settings()
    if not settings.instagram_access_token:
        return {}

    url = (
        f"{settings.graph_api_base_url.rstrip('/')}/"
        f"{settings.graph_api_version}/{igsid}"
    )
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(
                url,
                params={"fields": "name,username"},
                headers={"Authorization": f"Bearer {settings.instagram_access_token}"},
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError:
        logger.warning("Não consegui buscar o perfil de %s", igsid)
        return {}


def _send(recipient_id: str, message: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.instagram_access_token or not settings.instagram_id:
        raise RuntimeError("INSTAGRAM_USER_ID e INSTAGRAM_ACCESS_TOKEN são obrigatórios")

    payload = {
        "recipient": {"id": recipient_id},
        "message": message,
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(
            settings.graph_messages_url,
            params={"access_token": settings.instagram_access_token},
            headers={
                "Authorization": f"Bearer {settings.instagram_access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as extra:
            logger.error("Falha ao enviar DM: %s", extra.response.text)
            raise
        return response.json()
