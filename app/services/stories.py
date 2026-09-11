from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import get_settings
from app.services import vision
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

    description = vision.describe(media_url, _DESCRIBE_PROMPT)
    if not description:
        return None
    story_context.save(story_id, description, kind="story")
    logger.info("Story %s descrito: %s", story_id, description)
    return description


def sync_active_stories() -> list[str]:
    """Lê os stories ativos da conta e descreve os que ainda não conhecemos."""
    settings = get_settings()
    account_id, token = settings.stories_account
    if not settings.story_context_enabled or not token or not account_id:
        return []

    url = (
        f"{settings.graph_api_base_url.rstrip('/')}/"
        f"{settings.graph_api_version}/{account_id}/stories"
    )
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                url,
                params={
                    "fields": "id,media_type,media_url,thumbnail_url,timestamp",
                    "access_token": token,
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


_SYNC_MARKER = "_last_story_sync"


def maybe_sync() -> None:
    """Atualiza os stories de tempo em tempo, aproveitando o tráfego das DMs.

    Cron na Vercel no plano free roda uma vez por dia, o que é pouco para story.
    Então quem dispara é a própria chegada de mensagem, com trava de tempo para
    não chamar a API do Instagram a cada DM.
    """
    settings = get_settings()
    if not settings.story_context_enabled:
        return

    agora = datetime.now(timezone.utc)
    ultimo = story_context.get(_SYNC_MARKER)
    if ultimo:
        try:
            passou = agora - datetime.fromisoformat(ultimo)
            if passou < timedelta(minutes=settings.story_sync_minutes):
                return
        except ValueError:
            pass

    story_context.save(_SYNC_MARKER, agora.isoformat(), kind="meta")
    try:
        sync_active_stories()
    except Exception:
        logger.exception("Sync de stories falhou")


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
