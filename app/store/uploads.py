"""Arquivos de mídia pra publicar no Instagram.

Guarda no Postgres (Neon free) e serve em URL pública que a Meta baixa.
Se BLOB_READ_WRITE_TOKEN existir, prefere Vercel Blob (1 GB free).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.store.memory import _postgres, _postgres_dsn, _sqlite

logger = logging.getLogger(__name__)

_TABLE_PG = """
CREATE TABLE IF NOT EXISTS media_uploads (
    id TEXT PRIMARY KEY,
    data BYTEA,
    mime TEXT NOT NULL,
    filename TEXT,
    blob_url TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL
)
"""

_TABLE_SQLITE = """
CREATE TABLE IF NOT EXISTS media_uploads (
    id TEXT PRIMARY KEY,
    data BLOB,
    mime TEXT NOT NULL,
    filename TEXT,
    blob_url TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)
"""

# Limite do body na Vercel Hobby ~4.5 MB. Deixa folga.
MAX_BYTES = 4 * 1024 * 1024

_local: dict[str, dict] = {}


def _ext_for(mime: str, filename: str | None) -> str:
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()[:8]
    guess = mimetypes.guess_extension(mime or "") or ".bin"
    return guess.lstrip(".")


def public_url(upload_id: str, mime: str = "", filename: str | None = None) -> str:
    """URL que a Meta (e o front) usam pra baixar o arquivo."""
    settings = get_settings()
    # Se já foi pro Blob, a URL pública é a do Blob.
    meta = get(upload_id)
    if meta and meta.get("blob_url"):
        return str(meta["blob_url"])
    ext = _ext_for(mime or (meta or {}).get("mime", ""), filename)
    return f"{settings.base_url}/media/uploads/{upload_id}.{ext}"


def get(upload_id: str) -> dict | None:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                "SELECT mime, filename, blob_url, size_bytes, data IS NOT NULL "
                "FROM media_uploads WHERE id = %s",
                (upload_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "mime": row[0],
            "filename": row[1],
            "blob_url": row[2],
            "size_bytes": row[3],
            "has_data": bool(row[4]),
        }
    if upload_id in _local:
        item = _local[upload_id]
        return {
            "mime": item["mime"],
            "filename": item.get("filename"),
            "blob_url": item.get("blob_url"),
            "size_bytes": item.get("size_bytes", 0),
            "has_data": bool(item.get("data")),
        }
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        row = conn.execute(
            "SELECT mime, filename, blob_url, size_bytes, data IS NOT NULL "
            "FROM media_uploads WHERE id = ?",
            (upload_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "mime": row["mime"],
        "filename": row["filename"],
        "blob_url": row["blob_url"],
        "size_bytes": row["size_bytes"],
        "has_data": bool(row[4]),
    }


def get_bytes(upload_id: str) -> tuple[bytes, str] | None:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                "SELECT data, mime, blob_url FROM media_uploads WHERE id = %s",
                (upload_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        data, mime, blob_url = row[0], row[1], row[2]
        if data:
            return bytes(data), mime
        if blob_url:
            r = httpx.get(blob_url, timeout=60, follow_redirects=True)
            r.raise_for_status()
            return r.content, mime
        return None
    if upload_id in _local:
        item = _local[upload_id]
        if item.get("data"):
            return item["data"], item["mime"]
        if item.get("blob_url"):
            r = httpx.get(item["blob_url"], timeout=60, follow_redirects=True)
            r.raise_for_status()
            return r.content, item["mime"]
        return None
    with _sqlite() as conn:
        conn.execute(_TABLE_SQLITE)
        row = conn.execute(
            "SELECT data, mime, blob_url FROM media_uploads WHERE id = ?",
            (upload_id,),
        ).fetchone()
    if not row:
        return None
    if row["data"]:
        return bytes(row["data"]), row["mime"]
    if row["blob_url"]:
        r = httpx.get(row["blob_url"], timeout=60, follow_redirects=True)
        r.raise_for_status()
        return r.content, row["mime"]
    return None


def _blob_token() -> str:
    return os.getenv("BLOB_READ_WRITE_TOKEN") or get_settings().blob_read_write_token


def generate_client_token(
    *,
    pathname: str,
    maximum_size_bytes: int = 100 * 1024 * 1024,
    allowed_content_types: list[str] | None = None,
) -> str:
    """Token curto pra o browser mandar o arquivo direto no Blob (sem passar na função)."""
    rw = _blob_token()
    if not rw:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN não configurada")
    partes = rw.split("_")
    if len(partes) < 4:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN inválida")
    store_id = partes[3]
    valid_until = int(datetime.now(timezone.utc).timestamp() * 1000) + 60 * 60 * 1000
    corpo = {
        "pathname": pathname,
        "maximumSizeInBytes": int(maximum_size_bytes),
        "allowedContentTypes": allowed_content_types
        or [
            "video/mp4",
            "video/quicktime",
            "video/webm",
            "video/x-m4v",
            "video/*",
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/*",
            "application/octet-stream",
        ],
        "validUntil": valid_until,
        "addRandomSuffix": True,
        "allowOverwrite": False,
    }
    payload = base64.b64encode(
        json.dumps(corpo, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    assinatura = hmac.new(rw.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    interno = base64.b64encode(f"{assinatura}.{payload}".encode("utf-8")).decode("ascii")
    return f"vercel_blob_client_{store_id}_{interno}"


def url_blob_publica(url: str) -> bool:
    host = (url or "").lower()
    if not host.startswith("https://"):
        return False
    return "blob.vercel-storage.com" in host or "/media/uploads/" in host


def _put_vercel_blob(pathname: str, data: bytes, mime: str) -> str | None:
    token = _blob_token()
    if not token:
        return None
    # API REST do Vercel Blob — sem depender de SDK Node.
    try:
        r = httpx.put(
            f"https://blob.vercel-storage.com/{pathname}",
            content=data,
            headers={
                "Authorization": f"Bearer {token}",
                "x-api-version": "7",
                "x-content-type": mime,
                "x-add-random-suffix": "1",
            },
            timeout=120,
        )
        if r.status_code >= 400:
            logger.warning("Blob put falhou: %s %s", r.status_code, r.text[:300])
            return None
        return r.json().get("url")
    except Exception:
        logger.exception("Blob put erro")
        return None


def save(data: bytes, mime: str, filename: str | None = None) -> dict:
    """Salva o arquivo e devolve id + url pública."""
    if not data:
        raise ValueError("arquivo vazio")
    if len(data) > MAX_BYTES:
        raise ValueError(
            f"Arquivo maior que {MAX_BYTES // (1024 * 1024)} MB. "
            "No plano free da Vercel o upload direto tem esse teto — "
            "pra reel grande, cole a URL do vídeo no formulário."
        )

    upload_id = uuid.uuid4().hex
    mime = mime or "application/octet-stream"
    ext = _ext_for(mime, filename)
    pathname = f"uploads/{upload_id}.{ext}"
    blob_url = _put_vercel_blob(pathname, data, mime)
    now = datetime.now(timezone.utc)

    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(_TABLE_PG)
            cur.execute(
                """
                INSERT INTO media_uploads
                    (id, data, mime, filename, blob_url, size_bytes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    upload_id,
                    None if blob_url else data,
                    mime,
                    filename,
                    blob_url,
                    len(data),
                    now,
                ),
            )
    else:
        try:
            with _sqlite() as conn:
                conn.execute(_TABLE_SQLITE)
                conn.execute(
                    """
                    INSERT INTO media_uploads
                        (id, data, mime, filename, blob_url, size_bytes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        upload_id,
                        None if blob_url else data,
                        mime,
                        filename,
                        blob_url,
                        len(data),
                        now.isoformat(),
                    ),
                )
        except Exception:
            _local[upload_id] = {
                "data": None if blob_url else data,
                "mime": mime,
                "filename": filename,
                "blob_url": blob_url,
                "size_bytes": len(data),
            }

    url = blob_url or public_url(upload_id, mime, filename)
    return {
        "id": upload_id,
        "url": url,
        "mime": mime,
        "size_bytes": len(data),
        "via": "blob" if blob_url else "neon",
    }
