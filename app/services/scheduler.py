"""Publica o que já passou da hora marcada."""

from __future__ import annotations

import logging
from typing import Any

from app.services import previews, publish
from app.store import schedule

logger = logging.getLogger(__name__)


def process_due() -> dict[str, Any]:
    itens = schedule.due()
    feitos: list[dict] = []
    for item in itens:
        schedule.mark(item["id"], status="publishing")
        try:
            result = _publicar(item)
            schedule.mark(
                item["id"],
                status="published",
                ig_media_id=result.media_id,
            )
            feitos.append({"id": item["id"], "ok": True, "media_id": result.media_id})
            logger.info("Agendado %s publicado media=%s", item["id"], result.media_id)
        except Exception as erro:  # noqa: BLE001
            schedule.mark(item["id"], status="failed", error=str(erro)[:500])
            feitos.append({"id": item["id"], "ok": False, "erro": str(erro)[:300]})
            logger.exception("Falha ao publicar agendado %s", item["id"])
    return {"due": len(itens), "resultados": feitos}


def _publicar(item: dict) -> publish.PublishResult:
    kind = item["kind"]
    url = item["media_url"]
    caption = item.get("caption") or ""
    if kind == "previas":
        mid = previews.publicar(item)
        return publish.PublishResult(
            kind="story",
            container_id="telegram",
            media_id=mid,
            status="published",
            raw={"telegram": True},
        )
    if kind == "feed":
        return publish.publish("feed", image_url=url, caption=caption)
    if kind == "reels":
        return publish.publish(
            "reels",
            video_url=url,
            caption=caption,
            share_to_feed=bool(item.get("share_to_feed", True)),
        )
    if _parece_video(url):
        return publish.publish("story", video_url=url)
    return publish.publish("story", image_url=url)


def _parece_video(url: str) -> bool:
    u = (url or "").lower().split("?", 1)[0]
    return u.endswith((".mp4", ".mov", ".m4v", ".webm"))
