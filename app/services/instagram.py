from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_text_message(recipient_id: str, text: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.instagram_access_token or not settings.instagram_id:
        raise RuntimeError("INSTAGRAM_USER_ID e INSTAGRAM_ACCESS_TOKEN são obrigatórios")

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text[:1000]},
    }
    with httpx.Client(timeout=20) as client:
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
