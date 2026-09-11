from __future__ import annotations

import logging
import re
import unicodedata

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

# Nome que dá para falar em voz alta sem soar estranho.
_SPEAKABLE_NAME = re.compile(r"^[A-Za-zÀ-ÿ]{3,12}$")

_NOT_A_NAME = {
    "the",
    "oficial",
    "official",
    "insta",
    "real",
    "user",
    "sr",
    "sra",
    "dr",
    "dra",
}


def first_speakable_name(profile: dict) -> str | None:
    """Devolve o primeiro nome, se for simples o bastante para falar."""
    raw = (profile.get("name") or "").strip()
    if not raw:
        return None

    first = raw.split()[0]
    if not _SPEAKABLE_NAME.match(first):
        return None
    if first.lower() in _NOT_A_NAME:
        return None
    # Nome com acento é falável; símbolo e emoji já foram barrados pelo regex.
    normalized = unicodedata.normalize("NFKD", first)
    if not normalized.encode("ascii", "ignore").decode():
        return None
    return first.capitalize()


def should_use_voice(user_text: str, reply: str, incoming_is_audio: bool) -> bool:
    settings = get_settings()
    if not settings.voice_ready:
        return False
    if _URL.search(reply):
        # Link em áudio é inútil: a pessoa não consegue clicar.
        return False
    if len(reply) > settings.voice_max_chars:
        return False
    if incoming_is_audio:
        return True
    return bool(_HOT_PATTERNS.search(user_text))


def build_audio_url(text: str) -> str | None:
    """Gera o áudio, guarda e devolve a URL pública que o Instagram vai baixar."""
    settings = get_settings()
    clip = elevenlabs.synthesize(_strip_for_speech(text))
    if not clip:
        return None
    clip_id = media.save_audio(clip.data, clip.mime)
    return f"{settings.base_url}/media/audio/{clip_id}.{clip.extension}"


def _strip_for_speech(text: str) -> str:
    """Tira o que não se fala em voz alta: emoji e risada digitada."""
    without_emoji = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text)
    spoken = re.sub(r"\bk{3,}\b", "hahaha", without_emoji, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", spoken).strip()
