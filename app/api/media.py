from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from app.store import media

router = APIRouter(include_in_schema=False)


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
