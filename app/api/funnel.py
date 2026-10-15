"""API e tela do funil (React Flow)."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import ROOT_DIR, get_settings
from app.services import funnel, straton, telegram, telegram_sales
from app.store import uploads

router = APIRouter(include_in_schema=False)
_DIST = ROOT_DIR / "app" / "static" / "fluxo"


def _tipo_fluxo(sufixo: str) -> str | None:
    tipos = {
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".css": "text/css",
        ".wasm": "application/wasm",
        ".html": "text/html",
        ".json": "application/json",
    }
    if sufixo.lower() in tipos:
        return tipos[sufixo.lower()]
    return mimetypes.guess_type(f"x{sufixo}")[0]


def _publicar_se_banner(node_id: str) -> dict | None:
    dados = funnel.load()
    for n in dados.get("nodes") or []:
        if str(n.get("id")) == str(node_id) and (n.get("type") or "") == "banner":
            return telegram_sales.sync_profile(force=True)
    return None


def _check(k: str) -> None:
    senha = get_settings().diary_password
    if not senha:
        raise HTTPException(status_code=503, detail="Defina DIARY_PASSWORD")
    if k != senha:
        raise HTTPException(status_code=403, detail="Senha incorreta")


class FunilBody(BaseModel):
    nodes: list
    edges: list


class AnexarBody(BaseModel):
    node_id: str
    campo: str
    url: str


@router.post("/v1/funil/blob-upload")
async def blob_upload(request: Request, k: str = Query("")) -> dict:
    """Troca token pro browser subir vídeo/foto direto no Blob (arquivos grandes)."""
    _check(k)
    try:
        body = await request.json()
    except Exception as erro:
        raise HTTPException(status_code=400, detail="JSON inválido") from erro
    tipo = body.get("type")
    if tipo == "blob.generate-client-token":
        pathname = str((body.get("payload") or {}).get("pathname") or "funil/arquivo.bin")
        try:
            token = uploads.generate_client_token(pathname=pathname)
        except RuntimeError as erro:
            raise HTTPException(status_code=503, detail=str(erro)) from erro
        return {"type": tipo, "clientToken": token}
    if tipo == "blob.upload-completed":
        return {"type": tipo, "response": "ok"}
    raise HTTPException(status_code=400, detail="evento blob inválido")


@router.post("/v1/funil/anexar")
def anexar(body: AnexarBody, k: str = Query("")) -> dict:
    _check(k)
    if body.campo not in {"photo_url", "video_url"}:
        raise HTTPException(status_code=400, detail="campo inválido")
    if not uploads.url_blob_publica(body.url):
        raise HTTPException(status_code=400, detail="URL de mídia inválida")
    try:
        funnel.anexar_midia(body.node_id, body.campo, body.url)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    kind = "video" if body.campo == "video_url" else "photo"
    id_campo = "video_file_id" if kind == "video" else "photo_file_id"
    file_id = telegram_sales.cachear_na_telegram(body.url, kind)
    if file_id:
        funnel.anexar_midia(body.node_id, id_campo, file_id)
    perfil = _publicar_se_banner(body.node_id)
    return {"ok": True, "url": body.url, "file_id": bool(file_id), "perfil": perfil}


@router.get("/v1/funil")
def ler(k: str = Query("")) -> dict:
    _check(k)
    dados = funnel.load()
    dados["gaps_hours"] = list(funnel.rmk_gaps_hours())
    return dados


@router.put("/v1/funil")
def gravar(body: FunilBody, k: str = Query("")) -> dict:
    _check(k)
    salvo = funnel.save({"nodes": body.nodes, "edges": body.edges})
    salvo["gaps_hours"] = list(funnel.rmk_gaps_hours())
    salvo["perfil"] = telegram_sales.sync_profile()
    return salvo


@router.post("/v1/funil/publicar-perfil")
def publicar_perfil(k: str = Query("")) -> dict:
    _check(k)
    return telegram_sales.sync_profile()


@router.post("/v1/funil/midia-limpar")
def limpar_midia(
    k: str = Query(""),
    node_id: str = Query(""),
    campo: str = Query(""),
) -> dict:
    _check(k)
    try:
        funnel.anexar_midia(node_id, campo, "")
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    perfil = _publicar_se_banner(node_id)
    return {"ok": True, "perfil": perfil}


@router.post("/v1/funil/midia")
async def midia(
    k: str = Form(...),
    node_id: str = Form(...),
    campo: str = Form(...),
    arquivo: UploadFile = File(...),
) -> dict:
    _check(k)
    if campo not in {"photo_url", "video_url"}:
        raise HTTPException(status_code=400, detail="campo inválido")
    dados = await arquivo.read()
    mime = arquivo.content_type or ""
    if not mime or mime == "application/octet-stream":
        mime = mimetypes.guess_type(arquivo.filename or "")[0] or "application/octet-stream"
    try:
        salvo = uploads.save(dados, mime, arquivo.filename or "midia.bin")
        funnel.anexar_midia(node_id, campo, salvo["url"])
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    perfil = _publicar_se_banner(node_id)
    return {
        "ok": True,
        "url": salvo["url"],
        "node_id": node_id,
        "campo": campo,
        "via": salvo.get("via"),
        "perfil": perfil,
    }


@router.post("/v1/funil/video")
async def video(k: str = Form(...), arquivo: UploadFile = File(...)) -> dict:
    _check(k)
    dados = await arquivo.read()
    mime = arquivo.content_type or ""
    if not mime or mime == "application/octet-stream":
        mime = mimetypes.guess_type(arquivo.filename or "")[0] or "application/octet-stream"
    try:
        salvo = uploads.save(
            dados,
            mime,
            arquivo.filename or "midia.bin",
        )
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    return salvo


@router.post("/v1/funil/preparar-midia")
def preparar_midia(k: str = Query("")) -> dict:
    _check(k)
    return telegram_sales.preparar_midias()


@router.post("/v1/funil/test-start")
def test_start(k: str = Query("")) -> dict:
    _check(k)
    settings = get_settings()
    destino = settings.chat_dono_privado()
    if not destino:
        raise HTTPException(status_code=400, detail="Sem chat de alerta pra testar")
    via = telegram_sales._enviar_start(str(destino), username=None, first_name="Teste")
    return {"ok": True, "via": via}


@router.post("/v1/funil/test-pix")
def test_pix(k: str = Query("")) -> dict:
    _check(k)
    settings = get_settings()
    chave = uuid.uuid4().hex
    destino = settings.chat_dono_privado()
    dados = straton.create_cashin(
        amount=settings.active_price_amount(),
        external_id=f"{telegram_sales.REF_PREFIX}{destino or 'teste'}:{chave[:10]}",
        description="Priv da Lívia — teste do funil",
        customer_name="Teste funil",
        idempotency_key=chave,
    )
    codigo = str(dados.get("pix_code") or dados.get("brcode") or "")
    qr = str(dados.get("qr_code") or dados.get("qr_code_url") or "")
    enviado = False
    if destino and codigo:
        telegram.send_text_message(
            destino,
            "teste do funil — PIX gerado:\n\n" + codigo[:500],
            reply_markup=telegram_sales._botoes_venda(),
        )
        enviado = True
    return {
        "ok": bool(codigo),
        "enviado_telegram": enviado,
        "tem_qr": qr.startswith("http"),
        "tx": dados.get("id") or dados.get("transaction_id"),
        "pix_preview": (codigo[:12] + "…") if codigo else "",
    }


@router.post("/v1/funil/test-rmk")
def test_rmk(k: str = Query("")) -> dict:
    _check(k)
    # Não usa o chat pessoal como lead: RMK é só pra cliente.
    return telegram_sales.process_due(limit=10)


@router.get("/fluxo")
def pagina() -> FileResponse:
    index = _DIST / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Build do fluxo não encontrado")
    return FileResponse(
        index,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@router.get("/fluxo/{resto:path}")
def asset(resto: str):
    alvo = (_DIST / resto).resolve()
    if not str(alvo).startswith(str(_DIST.resolve())) or not alvo.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(
        alvo,
        media_type=_tipo_fluxo(alvo.suffix),
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
