"""Jobs externos no cron-job.org — o Hobby da Vercel só deixa um cron por dia."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

API = "https://api.cron-job.org"
TITULO_RMK = "hermes-rmk"
TITULO_PIX = "hermes-straton-pending"
TITULO_PREVIAS = "hermes-previas-semana"


def _chave() -> str:
    return (get_settings().cronjobs_api_key or "").strip()


def _base() -> str:
    return (get_settings().base_url or "https://dm-ia-hermes.vercel.app").rstrip("/")


def _bearer() -> str:
    s = get_settings()
    return (s.cron_secret or s.diary_password or "").strip()


def _headers_api() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_chave()}",
        "Content-Type": "application/json",
    }


def _minutos(passo: int) -> list[int]:
    return list(range(0, 60, passo))


def _payload(titulo: str, caminho: str, minutos: list[int]) -> dict[str, Any]:
    return {
        "title": titulo,
        "url": f"{_base()}{caminho}",
        "enabled": True,
        "saveResponses": True,
        "requestTimeout": 60,
        "requestMethod": 0,
        "schedule": {
            "timezone": "America/Sao_Paulo",
            "expiresAt": 0,
            "hours": [-1],
            "minutes": minutos,
            "mdays": [-1],
            "months": [-1],
            "wdays": [-1],
        },
        "extendedData": {
            "headers": {
                "Authorization": f"Bearer {_bearer()}",
                "X-Cron-Secret": _bearer(),
            }
        },
        "notification": {
            "onFailure": True,
            "onFailureCount": 2,
            "onSuccess": False,
        },
    }


def _payload_semanal(titulo: str, caminho: str) -> dict[str, Any]:
    corpo = _payload(titulo, caminho, [0])
    corpo["schedule"] = {
        "timezone": "America/Sao_Paulo",
        "expiresAt": 0,
        "hours": [18],
        "minutes": [0],
        "mdays": [-1],
        "months": [-1],
        "wdays": [1],
    }
    return corpo


def jobs_desejados() -> list[dict[str, Any]]:
    return [
        _payload(TITULO_RMK, "/v1/cron/rmk", _minutos(5)),
        _payload(TITULO_PIX, "/v1/cron/straton-pending", _minutos(10)),
        _payload_semanal(TITULO_PREVIAS, "/v1/cron/previas-semana"),
    ]


def listar() -> list[dict[str, Any]]:
    if not _chave():
        raise RuntimeError("CRONJOBS_API_KEY vazia")
    with httpx.Client(timeout=20) as client:
        r = client.get(f"{API}/jobs", headers=_headers_api())
        r.raise_for_status()
        return list((r.json() or {}).get("jobs") or [])


def ensure() -> dict[str, Any]:
    """Cria ou atualiza os jobs de RMK e PIX pendente."""
    if not _chave():
        return {"ok": False, "erro": "sem_chave"}
    if not _bearer():
        return {"ok": False, "erro": "sem_segredo"}
    existentes = {str(j.get("title") or ""): j for j in listar()}
    feitos: list[dict[str, Any]] = []
    with httpx.Client(timeout=20) as client:
        for wanted in jobs_desejados():
            titulo = str(wanted["title"])
            atual = existentes.get(titulo)
            if atual and atual.get("jobId"):
                jid = int(atual["jobId"])
                r = client.patch(
                    f"{API}/jobs/{jid}",
                    headers=_headers_api(),
                    json={"job": wanted},
                )
                r.raise_for_status()
                feitos.append({"title": titulo, "jobId": jid, "acao": "atualizado"})
            else:
                r = client.put(
                    f"{API}/jobs",
                    headers=_headers_api(),
                    json={"job": wanted},
                )
                r.raise_for_status()
                jid = int((r.json() or {}).get("jobId") or 0)
                feitos.append({"title": titulo, "jobId": jid, "acao": "criado"})
            time.sleep(1.2)
    logger.info("cron-job.org: %s", feitos)
    return {"ok": True, "jobs": feitos}
