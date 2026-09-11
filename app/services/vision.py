from __future__ import annotations

import base64
import logging

import httpx
from openai import OpenAI, OpenAIError

from app.config import get_settings

logger = logging.getLogger(__name__)


def fetch(media_url: str) -> tuple[bytes, str] | None:
    """Baixa a mídia. As URLs do Instagram são de CDN e expiram rápido."""
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get(media_url)
            response.raise_for_status()
            mime = response.headers.get("content-type", "").split(";")[0]
            return response.content, mime
    except httpx.HTTPError:
        logger.warning("Não consegui baixar a mídia")
        return None


def describe(media_url: str, prompt: str) -> str | None:
    """Descreve uma imagem com o modelo de visão."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    baixado = fetch(media_url)
    if not baixado:
        return None
    media, mime = baixado

    if not mime.startswith("image/"):
        logger.info("Mídia é %s, o modelo de visão não lê", mime or "desconhecido")
        return None

    data_url = f"data:{mime};base64,{base64.b64encode(media).decode()}"
    try:
        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        completion = client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=90,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        return (completion.choices[0].message.content or "").strip() or None
    except OpenAIError:
        logger.exception("Falha ao descrever a imagem")
        return None


def transcribe(media_url: str) -> str | None:
    """Transcreve um áudio recebido na DM."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    baixado = fetch(media_url)
    if not baixado:
        return None
    media, mime = baixado

    nome = "audio.mp4"
    if "aac" in mime:
        nome = "audio.aac"
    elif "wav" in mime:
        nome = "audio.wav"
    elif "ogg" in mime:
        nome = "audio.ogg"
    elif "mpeg" in mime or "mp3" in mime:
        nome = "audio.mp3"

    try:
        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        resultado = client.audio.transcriptions.create(
            model=settings.transcribe_model,
            file=(nome, media),
            language="pt",
        )
        return (getattr(resultado, "text", "") or "").strip() or None
    except OpenAIError:
        logger.exception("Falha ao transcrever o áudio")
        return None
