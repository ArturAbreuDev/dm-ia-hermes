from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.services import instagram, voice
from app.store import media

router = APIRouter(include_in_schema=False)


class VoicePreviewRequest(BaseModel):
    text: str


class VoiceSendRequest(BaseModel):
    recipient_id: str
    text: str
    output_format: str | None = None


@router.post("/v1/voice/send")
def voice_send(payload: VoiceSendRequest) -> dict[str, str]:
    """Manda um áudio de teste para um IGSID que já conversou com a conta."""
    url = voice.build_audio_url(payload.text, output_format=payload.output_format)
    if not url:
        raise HTTPException(status_code=502, detail="Não consegui gerar o áudio")
    try:
        instagram.send_audio_message(payload.recipient_id, url)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=exc.response.text) from exc
    return {"audio_url": url, "status": "enviado"}


@router.post("/v1/voice/preview")
def voice_preview(payload: VoicePreviewRequest) -> dict[str, str]:
    """Gera um áudio e devolve a URL, para conferir a voz sem mandar DM."""
    url = voice.build_audio_url(payload.text)
    if not url:
        raise HTTPException(status_code=502, detail="Não consegui gerar o áudio")
    return {"audio_url": url}


@router.head("/media/audio/{filename}")
@router.get("/media/audio/{filename}")
def get_audio(filename: str) -> Response:
    clip_id = filename.rsplit(".", 1)[0]
    found = media.get_audio(clip_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    data, mime = found
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Length": str(len(data)),
        },
    )
