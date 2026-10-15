"""Publicação orgânica no Instagram: feed, reels e stories.

Fluxo oficial da Meta (Content Publishing):
1. POST /{ig}/media  → cria o container
2. espera status_code = FINISHED (vídeo demora)
3. POST /{ig}/media_publish → publica
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

Kind = Literal["feed", "reels", "story"]


@dataclass
class PublishResult:
    kind: Kind
    container_id: str
    media_id: str | None
    status: str
    raw: dict[str, Any]


class PublishError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _base() -> tuple[str, str, str, dict[str, str]]:
    settings = get_settings()
    if not settings.instagram_access_token or not settings.instagram_id:
        raise PublishError("Instagram não configurado (token / user id)")
    base = (
        f"{settings.graph_api_base_url.rstrip('/')}/"
        f"{settings.graph_api_version}"
    )
    return (
        base,
        settings.instagram_id,
        settings.instagram_access_token,
        {"Authorization": f"Bearer {settings.instagram_access_token}"},
    )


def _post(path: str, data: dict[str, Any]) -> dict[str, Any]:
    base, _, token, headers = _base()
    payload = {**data, "access_token": token}
    with httpx.Client(timeout=90, headers=headers, follow_redirects=True) as client:
        r = client.post(f"{base}/{path}", data=payload)
    if r.status_code >= 400:
        raise PublishError(
            f"Falha POST {path}: {r.text[:400]}",
            status_code=r.status_code,
            body=r.text[:800],
        )
    return r.json()


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    base, _, token, headers = _base()
    q = {"access_token": token, **(params or {})}
    with httpx.Client(timeout=30, headers=headers, follow_redirects=True) as client:
        r = client.get(f"{base}/{path}", params=q)
    if r.status_code >= 400:
        raise PublishError(
            f"Falha GET {path}: {r.text[:400]}",
            status_code=r.status_code,
            body=r.text[:800],
        )
    return r.json()


def wait_until_ready(
    container_id: str,
    *,
    tentativas: int = 30,
    pausa: float = 2.0,
) -> str:
    """Espera o container ficar pronto pra publicar."""
    status = "IN_PROGRESS"
    for _ in range(tentativas):
        info = _get(container_id, {"fields": "status_code,status"})
        status = str(info.get("status_code") or "")
        if status in {"FINISHED", "ERROR", "EXPIRED", "PUBLISHED"}:
            return status
        time.sleep(pausa)
    return status


def create_feed_image(image_url: str, caption: str = "") -> str:
    """Container de foto no feed. Retorna o creation_id."""
    _, ig, _, _ = _base()
    data: dict[str, Any] = {"image_url": image_url}
    if caption:
        data["caption"] = caption[:2200]
    return str(_post(f"{ig}/media", data)["id"])


def create_story_image(image_url: str) -> str:
    _, ig, _, _ = _base()
    return str(
        _post(
            f"{ig}/media",
            {"image_url": image_url, "media_type": "STORIES"},
        )["id"]
    )


def create_story_video(video_url: str) -> str:
    _, ig, _, _ = _base()
    return str(
        _post(
            f"{ig}/media",
            {"video_url": video_url, "media_type": "STORIES"},
        )["id"]
    )


def create_reel(video_url: str, caption: str = "", share_to_feed: bool = True) -> str:
    _, ig, _, _ = _base()
    data: dict[str, Any] = {
        "video_url": video_url,
        "media_type": "REELS",
        "share_to_feed": "true" if share_to_feed else "false",
    }
    if caption:
        data["caption"] = caption[:2200]
    return str(_post(f"{ig}/media", data)["id"])


def publish_container(container_id: str) -> str:
    """Publica o container. Retorna o media_id do post/story/reel."""
    _, ig, _, _ = _base()
    out = _post(f"{ig}/media_publish", {"creation_id": container_id})
    return str(out["id"])


def publish(
    kind: Kind,
    *,
    image_url: str | None = None,
    video_url: str | None = None,
    caption: str = "",
    share_to_feed: bool = True,
) -> PublishResult:
    """Cria, espera e publica num passo só."""
    if kind == "feed":
        if not image_url:
            raise PublishError("feed precisa de image_url")
        container_id = create_feed_image(image_url, caption)
    elif kind == "story":
        if image_url:
            container_id = create_story_image(image_url)
        elif video_url:
            container_id = create_story_video(video_url)
        else:
            raise PublishError("story precisa de image_url ou video_url")
    elif kind == "reels":
        if not video_url:
            raise PublishError("reels precisa de video_url")
        container_id = create_reel(video_url, caption, share_to_feed=share_to_feed)
    else:
        raise PublishError(f"tipo desconhecido: {kind}")

    status = wait_until_ready(container_id)
    if status != "FINISHED":
        raise PublishError(
            f"container {container_id} não ficou pronto (status={status})"
        )

    media_id = publish_container(container_id)
    logger.info("Publicado %s container=%s media=%s", kind, container_id, media_id)
    return PublishResult(
        kind=kind,
        container_id=container_id,
        media_id=media_id,
        status="PUBLISHED",
        raw={"creation_id": container_id, "id": media_id},
    )
