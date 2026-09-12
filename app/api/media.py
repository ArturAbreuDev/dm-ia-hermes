from __future__ import annotations

import httpx
from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.services import instagram, voice
from app.store import media

router = APIRouter(include_in_schema=False)


class VoicePreviewRequest(BaseModel):
    text: str


class VoiceSendRequest(BaseModel):
    recipient_id: str
    text: str
    output_format: str | None = None


def _conferir_chave(chave: str | None) -> None:
    """Estas rotas mandam DM da conta dela. Não podem ficar abertas na internet."""
    esperada = get_settings().admin_key
    if not esperada:
        raise HTTPException(status_code=503, detail="DIARY_PASSWORD não configurada")
    if chave != esperada:
        raise HTTPException(status_code=403, detail="Chave inválida")


@router.post("/v1/voice/send-file")
async def voice_send_file(
    recipient_id: str,
    arquivo: UploadFile = File(...),
    k: str | None = None,
) -> dict[str, str]:
    """Manda um áudio já pronto, exatamente como ele está.

    Serve para o áudio que foi escutado e aprovado antes: gerar de novo passaria
    pelo diretor de voz outra vez e o resultado poderia sair diferente.
    """
    _conferir_chave(k)
    dados = await arquivo.read()
    if not dados:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    mime = arquivo.content_type or "audio/wav"
    extensao = "wav" if "wav" in mime else (arquivo.filename or "a.bin").rsplit(".", 1)[-1]
    clip_id = media.save_audio(dados, mime)
    url = f"{get_settings().base_url}/media/audio/{clip_id}.{extensao}"
    try:
        instagram.send_audio_message(recipient_id, url)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=exc.response.text) from exc
    return {"audio_url": url, "status": "enviado"}


@router.post("/v1/voice/send")
def voice_send(payload: VoiceSendRequest, k: str | None = None) -> dict[str, str]:
    """Manda um áudio de teste para um IGSID que já conversou com a conta."""
    _conferir_chave(k)
    url = voice.build_audio_url(payload.text, output_format=payload.output_format)
    if not url:
        raise HTTPException(status_code=502, detail="Não consegui gerar o áudio")
    try:
        instagram.send_audio_message(payload.recipient_id, url)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=exc.response.text) from exc
    return {"audio_url": url, "status": "enviado"}


@router.post("/v1/voice/preview")
def voice_preview(payload: VoicePreviewRequest, k: str | None = None) -> dict[str, str]:
    """Gera um áudio e devolve a URL, para conferir a voz sem mandar DM."""
    _conferir_chave(k)
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
