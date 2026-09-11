from __future__ import annotations

import logging
import re

from app.config import get_settings
from app.services import elevenlabs
from app.store import media

logger = logging.getLogger(__name__)

# Sinais de que a pessoa passou de curiosa para compradora.
_HOT_PATTERNS = re.compile(
    r"\b("
    r"vende|vendendo|venda|"
    r"conte[úu]do|pack|nudes?|foto[s]?|v[íi]deo[s]?|"
    r"quanto|pre[çc]o|valor|custa|"
    r"compr(o|ar|a)|paga(r|mento)|pix|"
    r"quero|link|telegram|assinar|assinatura"
    r")\b",
    re.IGNORECASE,
)

_URL = re.compile(r"https?://\S+")


def should_use_voice(user_text: str, reply: str, incoming_is_audio: bool) -> bool:
    if not get_settings().voice_ready:
        return False
    if _URL.search(reply):
        # Link em áudio é inútil: a pessoa não consegue clicar.
        return False
    if len(reply) > get_settings().voice_max_chars:
        return False
    if incoming_is_audio:
        return True
    return bool(_HOT_PATTERNS.search(user_text))


def build_audio_url(text: str) -> str | None:
    """Gera o áudio, guarda e devolve a URL pública que o Instagram vai baixar."""
    settings = get_settings()
    audio = elevenlabs.synthesize_wav(_strip_for_speech(text))
    if not audio:
        return None
    clip_id = media.save_audio(audio)
    return f"{settings.base_url}/media/audio/{clip_id}.wav"


def _strip_for_speech(text: str) -> str:
    """Tira o que não se fala em voz alta: emoji e risada digitada."""
    without_emoji = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text)
    spoken = re.sub(r"\bk{3,}\b", "hahaha", without_emoji, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", spoken).strip()
