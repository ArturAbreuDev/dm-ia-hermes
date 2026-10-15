from __future__ import annotations

import json
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
    result = payload.get("result")
    return result if isinstance(result, dict) else (result or {})


def send_photo_url(
    chat_id: str | int,
    photo_url: str,
    caption: str | None = None,
    *,
    reply_markup: dict[str, Any] | None = None,
    protect_content: bool = False,
    timeout: float = 20,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        payload["caption"] = caption[:1024]
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if protect_content:
        payload["protect_content"] = True
    with httpx.Client(timeout=timeout) as client:
        response = client.post(_api_url("sendPhoto"), json=payload)
        return _raise_for_telegram(response)


def send_video_url(
    chat_id: str | int,
    video_url: str,
    caption: str | None = None,
    *,
    reply_markup: dict[str, Any] | None = None,
    protect_content: bool = False,
    timeout: float = 20,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "video": video_url,
        "supports_streaming": True,
    }
    if caption:
        payload["caption"] = caption[:1024]
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if protect_content:
        payload["protect_content"] = True
    with httpx.Client(timeout=timeout) as client:
        response = client.post(_api_url("sendVideo"), json=payload)
        return _raise_for_telegram(response)


def send_video_bytes(
    chat_id: str | int,
    data: bytes,
    filename: str = "video.mp4",
    caption: str | None = None,
    *,
    reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    form: dict[str, Any] = {"chat_id": str(chat_id), "supports_streaming": "true"}
    if caption:
        form["caption"] = caption[:1024]
    if reply_markup:
        form["reply_markup"] = json.dumps(reply_markup)
    with httpx.Client(timeout=120) as client:
        response = client.post(
            _api_url("sendVideo"),
            data=form,
            files={"video": (filename, data, "video/mp4")},
        )
        return _raise_for_telegram(response)


def send_photo_bytes(
    chat_id: str | int,
    data: bytes,
    filename: str = "foto.jpg",
    caption: str | None = None,
    *,
    reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    form: dict[str, Any] = {"chat_id": str(chat_id)}
    if caption:
        form["caption"] = caption[:1024]
    if reply_markup:
        form["reply_markup"] = json.dumps(reply_markup)
    mime = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
    with httpx.Client(timeout=12) as client:
        response = client.post(
            _api_url("sendPhoto"),
            data=form,
            files={"photo": (filename, data, mime)},
        )
        return _raise_for_telegram(response)


def create_chat_invite_link(
    *,
    name: str = "vip",
    member_limit: int | None = 1,
    chat_id: str | int | None = None,
) -> str | None:
    """Convite do grupo. Sem member_limit = ilimitado (prévias)."""
    settings = get_settings()
    alvo = chat_id or settings.telegram_group_chat_id
    if not alvo:
        return None
    payload: dict[str, Any] = {"chat_id": alvo, "name": name[:32]}
    if member_limit is not None:
        payload["member_limit"] = member_limit
    with httpx.Client(timeout=20) as client:
        response = client.post(_api_url("createChatInviteLink"), json=payload)
        result = _raise_for_telegram(response)
    return str(result.get("invite_link") or "") or None


def delete_message(chat_id: str | int, message_id: int) -> dict[str, Any]:
    with httpx.Client(timeout=20) as client:
        response = client.post(
            _api_url("deleteMessage"),
            json={"chat_id": chat_id, "message_id": message_id},
        )
        return _raise_for_telegram(response)


def pin_chat_message(chat_id: str | int, message_id: int) -> dict[str, Any]:
    with httpx.Client(timeout=20) as client:
        response = client.post(
            _api_url("pinChatMessage"),
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "disable_notification": True,
            },
        )
        return _raise_for_telegram(response)


def send_text_message(
    chat_id: str | int,
    text: str,
    *,
    reply_markup: dict[str, Any] | None = None,
    protect_content: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text[:4096]}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if protect_content:
        payload["protect_content"] = True
    with httpx.Client(timeout=20) as client:
        response = client.post(_api_url("sendMessage"), json=payload)
        return _raise_for_telegram(response)


def send_photo(
    chat_id: str | int,
    photo_path: str | Path,
    caption: str | None = None,
    *,
    reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(photo_path)
    if not path.exists():
        raise FileNotFoundError(f"Foto não encontrada: {path}")
    data: dict[str, Any] = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption[:1024]
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    with path.open("rb") as handle, httpx.Client(timeout=12) as client:
        response = client.post(
            _api_url("sendPhoto"),
            data=data,
            files={"photo": (path.name, handle, "image/jpeg")},
        )
        return _raise_for_telegram(response)


def answer_callback(callback_id: str, text: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text[:200]
    with httpx.Client(timeout=20) as client:
        response = client.post(_api_url("answerCallbackQuery"), json=payload)
        return _raise_for_telegram(response)


def set_my_name(name: str) -> dict[str, Any]:
    with httpx.Client(timeout=20) as client:
        return _raise_for_telegram(
            client.post(_api_url("setMyName"), json={"name": name[:64]})
        )


def set_my_description(description: str, language_code: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"description": description[:512]}
    if language_code:
        payload["language_code"] = language_code
    with httpx.Client(timeout=20) as client:
        return _raise_for_telegram(
            client.post(_api_url("setMyDescription"), json=payload)
        )


def set_my_short_description(text: str, language_code: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"short_description": text[:120]}
    if language_code:
        payload["language_code"] = language_code
    with httpx.Client(timeout=20) as client:
        return _raise_for_telegram(
            client.post(_api_url("setMyShortDescription"), json=payload)
        )


def set_my_commands(commands: list[dict[str, str]]) -> dict[str, Any]:
    with httpx.Client(timeout=20) as client:
        return _raise_for_telegram(
            client.post(_api_url("setMyCommands"), json={"commands": commands})
        )


def get_my_description(language_code: str = "") -> dict[str, Any]:
    params = {"language_code": language_code} if language_code else {}
    with httpx.Client(timeout=20) as client:
        return _raise_for_telegram(client.get(_api_url("getMyDescription"), params=params))


def get_my_short_description(language_code: str = "") -> dict[str, Any]:
    params = {"language_code": language_code} if language_code else {}
    with httpx.Client(timeout=20) as client:
        return _raise_for_telegram(
            client.get(_api_url("getMyShortDescription"), params=params)
        )


def get_my_name(language_code: str = "") -> dict[str, Any]:
    params = {"language_code": language_code} if language_code else {}
    with httpx.Client(timeout=20) as client:
        return _raise_for_telegram(client.get(_api_url("getMyName"), params=params))


def set_my_profile_photo_bytes(
    data: bytes, filename: str = "cover.jpg", mime: str = "image/jpeg"
) -> dict[str, Any]:
    mime = mime or "image/jpeg"
    with httpx.Client(timeout=40) as client:
        response = client.post(
            _api_url("setMyProfilePhoto"),
            data={"photo": json.dumps({"type": "static", "photo": "attach://pic"})},
            files={"pic": (filename, data, mime)},
        )
        if response.status_code < 400 and response.json().get("ok"):
            return _raise_for_telegram(response)
        response = client.post(
            _api_url("setMyProfilePhoto"),
            files={"photo": (filename, data, mime)},
        )
        return _raise_for_telegram(response)


def set_my_profile_photo(photo_path: str | Path) -> dict[str, Any]:
    path = Path(photo_path)
    if not path.exists():
        raise FileNotFoundError(f"Foto não encontrada: {path}")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return set_my_profile_photo_bytes(path.read_bytes(), path.name, mime)


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


def get_chat_member(user_id: str | int, chat_id: str | int | None = None) -> dict[str, Any] | None:
    """Situação de uma pessoa no grupo, direto da fonte.

    Só funciona com id numérico: a Bot API aceita @username em chat_id, mas
    nunca em user_id, e não existe método para resolver @ de pessoa para id.
    """
    settings = get_settings()
    alvo = chat_id or settings.telegram_group_chat_id
    if not alvo:
        return None
    with httpx.Client(timeout=20) as client:
        response = client.get(
            _api_url("getChatMember"), params={"chat_id": alvo, "user_id": user_id}
        )
    corpo = response.json()
    if not corpo.get("ok"):
        logger.info("getChatMember recusado para %s: %s", user_id, corpo.get("description"))
        return None
    return corpo.get("result") or {}


def is_in_group(user_id: str | int, chat_id: str | int | None = None) -> bool:
    membro = get_chat_member(user_id, chat_id)
    if not membro:
        return False
    status = membro.get("status")
    if status in {"creator", "administrator", "member"}:
        return True
    # "restricted" ainda pode estar dentro: quem decide é o is_member.
    return status == "restricted" and bool(membro.get("is_member"))


def set_webhook(
    url: str, secret_token: str, *, drop_pending: bool = False
) -> dict[str, Any]:
    """Assina os eventos do grupo.

    chat_member não vem por padrão: a doc diz que o bot precisa ser
    administrador E listar o tipo explicitamente em allowed_updates. E como
    allowed_updates é uma lista de permissão, o que não está aqui não chega.
    drop_pending só quando a URL muda — senão o Start que acabou de clicar some.
    """
    with httpx.Client(timeout=20) as client:
        response = client.post(
            _api_url("setWebhook"),
            json={
                "url": url,
                "secret_token": secret_token,
                "drop_pending_updates": drop_pending,
                "allowed_updates": [
                    "message",
                    "channel_post",
                    "callback_query",
                    "chat_member",
                    "my_chat_member",
                    "chat_join_request",
                ],
            },
        )
        return _raise_for_telegram(response)


def ensure_webhook() -> dict[str, Any]:
    """Religa o webhook com o secret atual (senão o botão Start não chega)."""
    import os

    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_webhook_secret:
        return {"ok": False, "motivo": "sem_token"}
    base = (settings.base_url or "").rstrip("/")
    if not base:
        host = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL") or ""
        if host:
            base = host if host.startswith("http") else f"https://{host}"
    if not base:
        return {"ok": False, "motivo": "sem_url"}
    url = f"{base}/webhooks/telegram"
    try:
        info = get_webhook_info()
        atual = (info.get("url") or "") if isinstance(info, dict) else ""
        permitidos = (info.get("allowed_updates") or []) if isinstance(info, dict) else []
        if atual == url and "channel_post" in permitidos:
            return {"ok": True, "url": url, "ja_ok": True}
        set_webhook(url, settings.telegram_webhook_secret, drop_pending=False)
        info = get_webhook_info()
        if isinstance(info, dict):
            return {"ok": True, "url": info.get("url") or url}
        return {"ok": True, "url": url}
    except Exception as erro:
        logger.exception("setWebhook falhou")
        return {"ok": False, "erro": str(erro)[:180]}


def get_chat(chat_id: str | int) -> dict[str, Any] | None:
    with httpx.Client(timeout=12) as client:
        response = client.get(_api_url("getChat"), params={"chat_id": chat_id})
    corpo = response.json()
    if not corpo.get("ok"):
        logger.info("getChat recusado: %s", corpo.get("description"))
        return None
    result = corpo.get("result")
    return result if isinstance(result, dict) else None


def get_webhook_info() -> dict[str, Any]:
    with httpx.Client(timeout=20) as client:
        return _raise_for_telegram(client.get(_api_url("getWebhookInfo")))


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
