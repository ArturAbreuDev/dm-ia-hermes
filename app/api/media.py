from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.services import voice
from app.store import media

router = APIRouter(include_in_schema=False)


class VoicePreviewRequest(BaseModel):
    text: str


@router.post("/v1/voice/preview")
def voice_preview(payload: VoicePreviewRequest) -> dict[str, str]:
    """Gera um áudio e devolve a URL, para conferir a voz sem mandar DM."""
    url = voice.build_audio_url(payload.text)
    if not url:
        raise HTTPException(status_code=502, detail="Não consegui gerar o áudio")
    return {"audio_url": url}


@router.get("/media/audio/{clip_id}.wav")
def get_audio(clip_id: str) -> Response:
    data = media.get_audio(clip_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    return Response(
        content=data,
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=86400"},
    )
