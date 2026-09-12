from __future__ import annotations

import logging
from dataclasses import dataclass

from app.services import stories, vision

logger = logging.getLogger(__name__)

_IMAGE_PROMPT = (
    "Alguém mandou esta imagem numa conversa de Instagram. Descreva em uma frase curta, em "
    "português do Brasil, o que aparece nela, de forma objetiva. Se for uma foto de pessoa, "
    "diga apenas algo como \"uma selfie dele\" sem descrever o corpo. Se houver texto na "
    "imagem, diga o que está escrito."
)

_MENTION_PROMPT = (
    "Esta é uma imagem de um story do Instagram em que alguém marcou o perfil da Lívia. "
    "Descreva em uma frase curta, em português do Brasil, o que aparece no story e o que está "
    "escrito nele. Seja objetiva e não descreva corpos."
)


@dataclass
class Incoming:
    """O que chegou na DM, já traduzido para texto que a IA entende."""

    text: str
    is_audio: bool = False
    story_reply: str | None = None
    kind: str = "texto"

    @property
    def is_media(self) -> bool:
        return self.kind != "texto"


def read(message: dict) -> Incoming:
    texto = (message.get("text") or "").strip()
    anexos = [item for item in (message.get("attachments") or []) if item]
    tipos = {item.get("type") for item in anexos}

    story_reply = _story_reply(message)

    # A pessoa marcou a Lívia no story dela.
    if "story_mention" in tipos:
        url = _payload_url(anexos, "story_mention")
        descricao = vision.describe(url, _MENTION_PROMPT) if url else None
        base = (
            f"[a pessoa te marcou no story dela: {descricao}]"
            if descricao
            else "[a pessoa te marcou no story dela]"
        )
        return Incoming(
            text=f"{base} {texto}".strip(),
            story_reply=story_reply,
            kind="story_mention",
        )

    if "audio" in tipos:
        url = _payload_url(anexos, "audio")
        transcricao = vision.transcribe(url) if url else None
        if transcricao:
            logger.info("Áudio transcrito: %s", transcricao)
            base = f'[a pessoa mandou um áudio dizendo] "{transcricao}"'
        else:
            base = "[a pessoa mandou um áudio e você não conseguiu ouvir]"
        return Incoming(
            text=f"{base} {texto}".strip(),
            is_audio=True,
            story_reply=story_reply,
            kind="audio",
        )

    if "image" in tipos:
        url = _payload_url(anexos, "image")
        descricao = vision.describe(url, _IMAGE_PROMPT) if url else None
        base = (
            f"[a pessoa mandou uma foto: {descricao}]"
            if descricao
            else "[a pessoa mandou uma foto]"
        )
        return Incoming(
            text=f"{base} {texto}".strip(), story_reply=story_reply, kind="imagem"
        )

    # Vídeo e post compartilhado vêm antes do texto puro de propósito: quando a
    # pessoa manda um vídeo com legenda, os dois chegam no mesmo evento, e antes
    # o texto vencia e o vídeo era descartado sem ela nem saber que veio algo.
    if tipos & {"video", "ig_reel", "reel"}:
        return Incoming(
            text=f"[a pessoa mandou um vídeo] {texto}".strip(),
            story_reply=story_reply,
            kind="video",
        )
    if "share" in tipos:
        return Incoming(
            text=f"[a pessoa compartilhou um post com você] {texto}".strip(),
            story_reply=story_reply,
            kind="share",
        )
    if tipos & {"like_heart"}:
        return Incoming(
            text=f"[a pessoa reagiu com um coração] {texto}".strip(),
            story_reply=story_reply,
            kind="reacao",
        )

    if texto:
        return Incoming(text=texto, story_reply=story_reply)

    outros = ", ".join(sorted(t for t in tipos if t)) or "desconhecido"
    return Incoming(text=f"[a pessoa mandou algo do tipo {outros}]", story_reply=story_reply, kind="outro")


def _payload_url(anexos: list[dict], tipo: str) -> str | None:
    for item in anexos:
        if item.get("type") == tipo:
            return ((item.get("payload") or {}).get("url")) or None
    return None


def _story_reply(message: dict) -> str | None:
    """Resposta a um story da Lívia: a doc traz id e url em reply_to.story."""
    story = ((message.get("reply_to") or {}).get("story")) or {}
    story_id, media_url = story.get("id"), story.get("url")
    if not story_id or not media_url:
        return None
    try:
        return stories.describe_story(story_id, media_url)
    except Exception:
        logger.exception("Falha ao descrever o story respondido")
        return None
