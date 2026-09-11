from __future__ import annotations

import io
import logging
import wave
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


@dataclass
class Clip:
    data: bytes
    extension: str
    mime: str


def synthesize(text: str, output_format: str | None = None) -> Clip | None:
    """Gera a fala no ElevenLabs.

    O formato vem de ELEVENLABS_OUTPUT_FORMAT. Se for PCM, montamos o container
    WAV aqui, porque o ElevenLabs devolve as amostras cruas.
    """
    settings = get_settings()
    if not settings.elevenlabs_api_key or not settings.elevenlabs_voice_id:
        return None

    output_format = output_format or settings.elevenlabs_output_format
    url = _API_URL.format(voice_id=settings.elevenlabs_voice_id)
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                url,
                params={"output_format": output_format},
                headers={
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": settings.elevenlabs_model,
                    "voice_settings": {
                        "stability": settings.elevenlabs_stability,
                        "use_speaker_boost": True,
                    },
                },
            )
            response.raise_for_status()
            audio = response.content
    except httpx.HTTPError:
        logger.exception("Falha ao gerar áudio no ElevenLabs")
        return None

    if not audio:
        return None

    if output_format.startswith("pcm_"):
        rate = int(output_format.removeprefix("pcm_"))
        return Clip(_wrap_pcm_in_wav(audio, rate), "wav", "audio/wav")
    if output_format.startswith("mp3_"):
        return Clip(audio, "mp3", "audio/mpeg")
    if output_format.startswith("opus_"):
        return Clip(audio, "ogg", "audio/ogg")
    return Clip(audio, "bin", "application/octet-stream")


def _wrap_pcm_in_wav(pcm: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()
