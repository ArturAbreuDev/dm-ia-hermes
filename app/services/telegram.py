from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _api_url(method: str) -> str:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN é obrigatório")
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


def _raise_for_telegram(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        response.raise_for_status()
        raise RuntimeError("Resposta inválida da API do Telegram")
    if not payload.get("ok"):
        logger.error("Telegram recusou o envio: %s", payload)
        raise RuntimeError(payload.get("description") or "Falha na API do Telegram")
    return payload.get("result") or {}


def send_text_message(chat_id: str | int, text: str) -> dict[str, Any]:
    with httpx.Client(timeout=20) as client:
        response = client.post(
            _api_url("sendMessage"),
            json={"chat_id": chat_id, "text": text[:4096]},
        )
        return _raise_for_telegram(response)


def send_voice_message(
    chat_id: str | int,
    audio_path: str | Path,
    caption: str | None = None,
) -> dict[str, Any]:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Áudio não encontrado: {path}")

    data: dict[str, Any] = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption[:1024]

    with path.open("rb") as handle, httpx.Client(timeout=60) as client:
        response = client.post(
            _api_url("sendVoice"),
            data=data,
            files={"voice": (path.name, handle, "audio/ogg")},
        )
        return _raise_for_telegram(response)


def get_recent_updates(limit: int = 20) -> list[dict[str, Any]]:
    with httpx.Client(timeout=20) as client:
        response = client.get(_api_url("getUpdates"), params={"limit": limit})
        result = _raise_for_telegram(response)
        return result if isinstance(result, list) else []


def find_chat_id(name_hint: str) -> int | None:
    hint = name_hint.strip().lower().lstrip("@")
    for update in reversed(get_recent_updates(100)):
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        from_user = message.get("from") or {}
        candidates = [
            str(chat.get("id") or ""),
            str(chat.get("username") or ""),
            str(chat.get("first_name") or ""),
            str(chat.get("last_name") or ""),
            f"{chat.get('first_name', '')} {chat.get('last_name', '')}".strip(),
            str(from_user.get("username") or ""),
            str(from_user.get("first_name") or ""),
            str(from_user.get("last_name") or ""),
            f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip(),
        ]
        if any(hint in value.lower() for value in candidates if value):
            chat_id = chat.get("id")
            return int(chat_id) if chat_id is not None else None
    return None
