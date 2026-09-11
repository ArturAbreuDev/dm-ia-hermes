from __future__ import annotations

import io
import logging
import wave

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def synthesize_wav(text: str) -> bytes | None:
    """Gera a fala no ElevenLabs e devolve um WAV.

    O Instagram só aceita aac, m4a, wav ou mp4, então pedimos PCM cru e
    montamos o container WAV aqui.
    """
    settings = get_settings()
    if not settings.elevenlabs_api_key or not settings.elevenlabs_voice_id:
        return None

    url = _API_URL.format(voice_id=settings.elevenlabs_voice_id)
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                url,
                params={"output_format": f"pcm_{settings.elevenlabs_sample_rate}"},
                headers={
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": settings.elevenlabs_model,
                },
            )
            response.raise_for_status()
            pcm = response.content
    except httpx.HTTPError:
        logger.exception("Falha ao gerar áudio no ElevenLabs")
        return None

    if not pcm:
        return None
    return _wrap_pcm_in_wav(pcm, settings.elevenlabs_sample_rate)


def _wrap_pcm_in_wav(pcm: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()
