from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from openai import OpenAI, OpenAIError

from app.config import get_settings
from app.store import story_context

logger = logging.getLogger(__name__)

_DESCRIBE_PROMPT = (
    "Esta é uma imagem de um story do Instagram da própria Lívia. Descreva em uma frase "
    "curta, em português do Brasil, o que ela está mostrando: onde parece estar, o que está "
    "fazendo, o que aparece escrito na tela. Escreva como uma anotação de diário na primeira "
    "pessoa, começando por um verbo. Exemplos: \"fui na Expointer ver os animais\", "
    "\"postei uma selfie no espelho de casa\", \"mostrei meu café da manhã\". "
    "Se houver texto na imagem, use essa informação, ela é a mais confiável. "
    "Não descreva o corpo dela e não comente a aparência. Só o contexto."
)


def describe_story(story_id: str, media_url: str) -> str | None:
    """Descreve um story e guarda a descrição.

    A doc da Meta proíbe guardar a mídia do story no servidor, então baixamos só
    para gerar a descrição e guardamos apenas o texto.
    """
    cached = story_context.get(story_id)
    if cached:
        return cached

    settings = get_settings()
    if not settings.openai_api_key or not settings.story_context_enabled:
        return None

    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get(media_url)
            response.raise_for_status()
            media = response.content
            mime = response.headers.get("content-type", "image/jpeg").split(";")[0]
    except httpx.HTTPError:
        logger.warning("Não consegui baixar o story %s", story_id)
        return None

    if not mime.startswith("image/"):
        # Vídeo não dá para mandar para o modelo de visão; fica sem descrição.
        logger.info("Story %s é %s, não descrevi", story_id, mime)
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
                        {"type": "text", "text": _DESCRIBE_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        description = (completion.choices[0].message.content or "").strip()
    except OpenAIError:
        logger.exception("Falha ao descrever o story %s", story_id)
        return None

    if not description:
        return None
    story_context.save(story_id, description, kind="story")
    logger.info("Story %s descrito: %s", story_id, description)
    return description


def sync_active_stories() -> list[str]:
    """Lê os stories ativos da conta e descreve os que ainda não conhecemos."""
    settings = get_settings()
    if not settings.story_context_enabled or not settings.instagram_access_token:
        return []

    url = (
        f"{settings.graph_api_base_url.rstrip('/')}/"
        f"{settings.graph_api_version}/{settings.instagram_id}/stories"
    )
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                url,
                params={
                    "fields": "id,media_type,media_url,thumbnail_url,timestamp",
                    "access_token": settings.instagram_access_token,
                },
            )
            response.raise_for_status()
            items: list[dict[str, Any]] = response.json().get("data") or []
    except httpx.HTTPError as extra:
        detail = getattr(getattr(extra, "response", None), "text", extra)
        logger.warning("Não consegui listar os stories: %s", detail)
        return []

    descritos = []
    for item in items:
        story_id = item.get("id")
        # Em vídeo a thumbnail é a única coisa que o modelo de visão consegue ler.
        media_url = item.get("thumbnail_url") or item.get("media_url")
        if not story_id or not media_url:
            continue
        description = describe_story(story_id, media_url)
        if description:
            descritos.append(description)
    return descritos


def prompt_block(replying_to: str | None = None) -> str:
    """Monta o pedaço do prompt que conta o que ela andou postando."""
    if not get_settings().story_context_enabled:
        return ""

    linhas = []
    if replying_to:
        linhas.append(
            f"A pessoa está respondendo a ESTE story seu: \"{replying_to}\".\n"
            "Responda sabendo disso, sem perguntar do que ela está falando. Essa descrição é a "
            "sua memória do story, não um texto para repetir: nunca copie essas palavras na "
            "resposta."
        )

    recentes = story_context.recent(limit=10)
    if recentes:
        diario = "\n".join(
            f"- {item['quando']}: {item['description']}" for item in recentes
        )
        linhas.append(f"Seus stories e acontecimentos recentes:\n{diario}")

    if not linhas:
        return ""
    return "\n\n".join(linhas)
