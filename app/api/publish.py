"""Rotas pra publicar feed / reels / stories (protegidas pela senha do diário)."""

from __future__ import annotations

from typing import Literal

from app.config import get_settings
from app.services import publish
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl, model_validator

router = APIRouter(tags=["Publicação"])

Kind = Literal["feed", "reels", "story"]


class PublishRequest(BaseModel):
    kind: Kind
    image_url: HttpUrl | None = None
    video_url: HttpUrl | None = None
    caption: str = Field(default="", max_length=2200)
    share_to_feed: bool = True

    @model_validator(mode="after")
    def _checa_midia(self):
        if self.kind == "feed" and not self.image_url:
            raise ValueError("feed precisa de image_url")
        if self.kind == "reels" and not self.video_url:
            raise ValueError("reels precisa de video_url")
        if self.kind == "story" and not self.image_url and not self.video_url:
            raise ValueError("story precisa de image_url ou video_url")
        return self


class PublishResponse(BaseModel):
    kind: Kind
    container_id: str
    media_id: str | None
    status: str


def _auth(k: str | None) -> None:
    settings = get_settings()
    if not settings.admin_key:
        raise HTTPException(status_code=503, detail="DIARY_PASSWORD não configurada")
    if k != settings.admin_key:
        raise HTTPException(status_code=403, detail="Chave inválida")


@router.post("/publish", response_model=PublishResponse)
def publicar(payload: PublishRequest, k: str | None = None) -> PublishResponse:
    """Publica na conta Instagram conectada.

    A mídia precisa estar numa URL pública HTTPS que a Meta consiga baixar.
    """
    _auth(k)
    try:
        result = publish.publish(
            payload.kind,
            image_url=str(payload.image_url) if payload.image_url else None,
            video_url=str(payload.video_url) if payload.video_url else None,
            caption=payload.caption,
            share_to_feed=payload.share_to_feed,
        )
    except publish.PublishError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return PublishResponse(
        kind=result.kind,
        container_id=result.container_id,
        media_id=result.media_id,
        status=result.status,
    )
