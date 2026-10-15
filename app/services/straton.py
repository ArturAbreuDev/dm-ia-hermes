"""Cliente da API pública da StratonBot (só o que a venda precisa)."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

BASE = "https://stratonbot.app/api/public/v1"


def _headers() -> dict[str, str] | None:
    chave = get_settings().straton_api_key
    if not chave:
        return None
    return {"Authorization": f"Bearer {chave}", "Accept": "application/json"}


def list_transactions(limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    """Lista cobranças. Sem chave configurada devolve lista vazia."""
    headers = _headers()
    if not headers:
        return []
    params: dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status
    try:
        r = httpx.get(
            f"{BASE}/transactions",
            params=params,
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json()
    except Exception:
        logger.exception("Falha ao listar transações Straton")
        return []
    return list((payload.get("data") or {}).get("items") or [])


def pending_bot_sales(limit: int = 50) -> list[dict[str, Any]]:
    """Cobranças do bot ainda abertas — é aí que a venda está caindo."""
    itens = list_transactions(limit=limit)
    return [
        i
        for i in itens
        if i.get("status") == "pending" and i.get("type") == "bot_sale"
    ]


def recent_expired_bot_sales(limit: int = 50) -> list[dict[str, Any]]:
    return [
        i
        for i in list_transactions(limit=limit)
        if i.get("status") == "expired" and i.get("type") == "bot_sale"
    ]


def create_cashin(
    *,
    amount: float,
    external_id: str,
    description: str,
    customer_name: str,
    idempotency_key: str,
    customer_document: str = "12345678900",
) -> dict[str, Any]:
    """Cria PIX na Straton. Devolve pix_code / qr_code / transaction_id."""
    headers = _headers()
    if not headers:
        raise RuntimeError("STRATON_API_KEY não configurada")
    corpo = {
        "amount": round(float(amount), 2),
        "external_id": external_id,
        "description": description[:120],
        "customer": {
            "name": (customer_name or "Cliente")[:80],
            "document": re.sub(r"\D", "", customer_document or "")[:14] or "12345678900",
        },
    }
    with httpx.Client(timeout=40) as client:
        r = client.post(
            f"{BASE}/cashin",
            headers={**headers, "Idempotency-Key": idempotency_key, "Content-Type": "application/json"},
            json=corpo,
        )
    if r.status_code >= 400:
        logger.warning("Straton cashin falhou: %s %s", r.status_code, r.text[:400])
        raise RuntimeError(f"Straton recusou o PIX ({r.status_code})")
    payload = r.json() if r.content else {}
    dados = payload.get("data") if isinstance(payload, dict) else None
    return dados if isinstance(dados, dict) else (payload if isinstance(payload, dict) else {})


def pix_hosted_url(dados: dict[str, Any]) -> str:
    """Se a Straton mandar uma página de pagamento, usamos. Senão, vazio."""
    for chave in ("payment_url", "checkout_url", "pix_url", "url", "link"):
        valor = dados.get(chave)
        if not isinstance(valor, str) or not valor.startswith("http"):
            continue
        baixo = valor.lower()
        if "qr" in chave or "qrserver" in baixo or baixo.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            continue
        return valor.strip()
    return ""
