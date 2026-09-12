from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from app.config import get_settings
from app.store import memory
from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Pagamentos"])

# Nomes de evento que significam "o dinheiro entrou", em várias plataformas.
_APROVADO = {
    "sale_approved",          # Kirvano
    "purchase_approved",      # Cakto
    "checkout.completed",     # AbacatePay
    "billing.paid",
    "payment.approved",
    "payment_confirmed",
    "order.paid",
    "pix.paid",
    "approved",
    "paid",
}

# Onde cada plataforma costuma deixar a referência livre que enviamos no link.
_CAMINHOS_DE_REF = (
    ("utm", "src"),                       # Kirvano
    ("data", "utm", "src"),
    ("data", "externalId"),               # AbacatePay
    ("data", "external_id"),
    ("data", "metadata", "ref"),          # Cakto
    ("data", "metadata", "igsid"),
    ("metadata", "ref"),
    ("metadata", "igsid"),
    ("external_id",),
    ("externalId",),
    ("ref",),
    ("client_reference_id",),
)


@router.post("/payments/webhook")
async def receive_payment(
    request: Request,
    x_webhook_signature: str | None = Header(default=None, alias="X-Webhook-Signature"),
) -> dict[str, Any]:
    """Confirma pagamento vindo da plataforma de checkout.

    Aceita o formato de várias plataformas de propósito: enquanto a decisão de
    qual usar não estiver tomada, o que importa é o endereço não mudar depois.
    """
    raw = await request.body()
    if not _autorizado(request, raw, x_webhook_signature):
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError as extra:
        raise HTTPException(status_code=400, detail="JSON inválido") from extra

    evento = _evento(payload)
    if not _esta_pago(payload):
        logger.info("Pagamento ignorado: evento=%s não é aprovação", evento)
        return {"status": "ignorado", "evento": evento}

    ref = _ref(payload)
    if not ref:
        # Venda real, mas sem como saber de quem. Fica no log para conferência.
        logger.warning(
            "Pagamento aprovado sem referência do lead: evento=%s payload=%s",
            evento,
            json.dumps(payload)[:800],
        )
        return {"status": "sem_referencia", "evento": evento}

    memory.mark_paid(ref)
    logger.info("Pagamento confirmado para IGSID=%s via evento=%s", ref, evento)
    return {"status": "pago", "igsid": ref, "evento": evento}


def _autorizado(request: Request, raw: bytes, assinatura: str | None) -> bool:
    segredo = get_settings().payment_webhook_secret
    if not segredo:
        # Sem segredo configurado o endpoint fica fechado, não aberto.
        logger.error("PAYMENT_WEBHOOK_SECRET não configurado; recusando o webhook")
        return False

    # Cada plataforma manda o segredo de um jeito. Aceitamos os três comuns.
    for chave in ("secret", "webhookSecret", "token"):
        se_vier = request.query_params.get(chave)
        if se_vier and hmac.compare_digest(se_vier, segredo):
            return True

    if assinatura:
        esperado = hmac.new(segredo.encode(), raw, hashlib.sha256).hexdigest()
        if hmac.compare_digest(assinatura.replace("sha256=", ""), esperado):
            return True

    try:
        corpo = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return False
    no_corpo = corpo.get("secret") or corpo.get("token")
    return bool(no_corpo) and hmac.compare_digest(str(no_corpo), segredo)


def _evento(payload: dict) -> str:
    for chave in ("event", "type", "status", "event_type"):
        valor = payload.get(chave) or (payload.get("data") or {}).get(chave)
        if isinstance(valor, str) and valor:
            return valor
    return "desconhecido"


def _esta_pago(payload: dict) -> bool:
    dados = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    candidatos = [
        payload.get("event"),
        payload.get("type"),
        payload.get("event_type"),
        payload.get("status"),
        dados.get("event"),
        dados.get("status"),
    ]
    return any(
        isinstance(v, str) and v.strip().lower() in _APROVADO for v in candidatos
    )


def _ref(payload: dict) -> str | None:
    for caminho in _CAMINHOS_DE_REF:
        atual: Any = payload
        for parte in caminho:
            if not isinstance(atual, dict):
                atual = None
                break
            atual = atual.get(parte)
        if isinstance(atual, str) and atual.strip():
            candidato = atual.strip()
            # IGSID é numérico e longo. Qualquer outra coisa não é o nosso lead.
            if candidato.isdigit() and len(candidato) >= 8:
                return candidato
            logger.info("Referência %r ignorada: não parece um IGSID", candidato[:60])
    return None
