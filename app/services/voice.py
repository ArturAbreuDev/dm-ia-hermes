from __future__ import annotations

import logging
import re
import unicodedata

from app.config import get_settings
from app.services import elevenlabs, voice_director
from app.store import media

logger = logging.getLogger(__name__)

# Sinais de que a pessoa passou de curiosa para compradora.
_HOT_PATTERNS = re.compile(
    r"(?:"
    r"\bvende\b|\bvendendo\b|\bvenda\b|"
    r"\bconte[úu]do\b|\bpack\b|\bpacks\b|\bnudes?\b|"
    r"quanto\s+(?:custa|[ée]|sai)|"
    r"quero\s+(?:compr\w*|assinar|o\s+pack|o\s+conte[úu]do)|"
    r"vou\s+compr\w*|"
    r"como\s+(?:funciona|fa[çc]o\s+pra\s+compr\w*)"
    r")",
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
    if not re.search(r"[aeiouáàãâéêíóôõú]", first, re.IGNORECASE):
        return None
    if re.search(r"(.)\1\1", first, re.IGNORECASE):
        return None
    # Nome com acento é falável; símbolo e emoji já foram barrados pelo regex.
    normalized = unicodedata.normalize("NFKD", first)
    if not normalized.encode("ascii", "ignore").decode():
        return None
    return first.capitalize()


def is_voice_moment(user_text: str, incoming_is_audio: bool) -> bool:
    """Decide, já na chegada da mensagem, se o caso pede áudio.

    Saber isso antes de gerar a resposta deixa a IA escrever um texto que
    funcione falado, começando pelo nome da pessoa.
    """
    if not get_settings().voice_ready:
        return False
    if incoming_is_audio:
        return True
    return bool(_HOT_PATTERNS.search(user_text))


def should_use_voice(user_text: str, reply: str, incoming_is_audio: bool) -> bool:
    if not is_voice_moment(user_text, incoming_is_audio):
        return False
    if _URL.search(reply):
        # Link em áudio é inútil: a pessoa não consegue clicar.
        return False
    return len(reply) <= get_settings().voice_max_chars


def build_audio_url(text: str, output_format: str | None = None) -> str | None:
    """Gera o áudio, guarda e devolve a URL pública que o Instagram vai baixar."""
    settings = get_settings()
    spoken = voice_director.direct_for_speech(_strip_for_speech(text))
    clip = elevenlabs.synthesize(spoken, output_format=output_format)
    if not clip:
        return None
    clip_id = media.save_audio(clip.data, clip.mime)
    return f"{settings.base_url}/media/audio/{clip_id}.{clip.extension}"


_EMOJI = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")
_LAUGH = re.compile(r"\b(?:k{3,}|h{3,}|(?:ha){2,}h?|rs{2,})\b", re.IGNORECASE)
# A gíria fica bonita na DM escrita, mas falada em voz alta soa péssima.
# Então tudo o que ela digita abreviado volta ao normal antes de virar áudio.
_ABBREVIATIONS = {
    r"\bvc\b": "você",
    r"\bvcs\b": "vocês",
    r"\btb\b": "também",
    r"\btbm\b": "também",
    r"\bpq\b": "porque",
    r"\bpqp\b": "puta que pariu",
    r"\bq\b": "que",
    r"\bmt\b": "muito",
    r"\bmto\b": "muito",
    r"\bmta\b": "muita",
    r"\bmsm\b": "mesmo",
    r"\bnsei\b": "não sei",
    r"\bntd\b": "nada",
    r"\bsla\b": "sei lá",
    r"\bvdd\b": "verdade",
    r"\bdps\b": "depois",
    r"\bagr\b": "agora",
    r"\bblz\b": "beleza",
    r"\bobg\b": "obrigada",
    r"\bhj\b": "hoje",
    r"\bamh\b": "amanhã",
    r"\bta\b": "tá",
    r"\btava\b": "tava",
    r"\bcmg\b": "comigo",
    r"\bctg\b": "contigo",
    r"\bfds\b": "fim de semana",
    r"\bss\b": "sim",
    r"\bnn\b": "não",
    r"\bqnd\b": "quando",
    r"\bqse\b": "quase",
    r"\btd\b": "tudo",
    r"\bnd\b": "nada",
    r"\bpfv\b": "por favor",
    r"R\$\s*": "",
}


def _strip_for_speech(text: str) -> str:
    """Prepara o texto para ser falado.

    O v3 lê a pontuação como direção de atuação: vírgula é respiro, reticência é
    hesitação, interrogação levanta a voz. Então vale mais ajustar a pontuação do
    que mexer nos parâmetros da voz.
    """
    spoken = _EMOJI.sub("", text)
    spoken = _LAUGH.sub("[laughs]", spoken)

    for pattern, replacement in _ABBREVIATIONS.items():
        spoken = re.sub(pattern, replacement, spoken, flags=re.IGNORECASE)

    spoken = re.sub(r"\s+", " ", spoken).strip()
    if not spoken:
        return ""

    spoken = re.sub(r"\.{4,}", "...", spoken)
    spoken = re.sub(r"([!?])\1{1,}", r"\1", spoken)
    spoken = re.sub(r"\s+([,.!?;:])", r"\1", spoken)
    spoken = re.sub(r"([,.!?;:])(?=[A-Za-zÀ-ÿ])", r"\1 ", spoken)

    # Sem ponto final o v3 corta a última palavra ou sobe o tom como se fosse pergunta.
    if spoken[-1] not in ".!?…":
        spoken += "."

    return re.sub(r"\s+", " ", spoken).strip()
