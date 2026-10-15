from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

from app.config import get_settings
from app.services import alert, ig_checkout, pix_rmk, telegram_sales
from app.store import memory, pedidos
from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Pagamentos"])

# Nomes de evento que significam "o dinheiro entrou", em várias plataformas.
_APROVADO = {
    "sale_approved",  # Kirvano
    "purchase_approved",  # Cakto
    "checkout.completed",  # AbacatePay
    "billing.paid",
    "payment.approved",
    "payment_confirmed",
    "order.paid",
    "pix.paid",
    "cashin.paid",  # StratonBot
    "approved",
    "paid",
}

_PENDENTE = {
    "cashin.pending",
    "pending",
}

_EXPIRADO = {
    "cashin.expired",
    "expired",
}

# Onde cada plataforma costuma deixar a referência livre que enviamos no link.
_CAMINHOS_DE_REF = (
    ("utm", "src"),  # Kirvano
    ("data", "utm", "src"),
    ("data", "externalId"),  # AbacatePay
    ("data", "external_id"),
    ("data", "metadata", "ref"),  # Cakto
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
    x_straton_signature: str | None = Header(
        default=None, alias="X-StratonBot-Signature"
    ),
    x_straton_timestamp: str | None = Header(
        default=None, alias="X-StratonBot-Timestamp"
    ),
    x_straton_event_id: str | None = Header(
        default=None, alias="X-StratonBot-Event-Id"
    ),
) -> dict[str, Any]:
    """Confirma pagamento / PIX pendente / PIX expirado.

    Aceita o formato de várias plataformas. A Straton assina com
    X-StratonBot-Signature sobre `{timestamp}.{body}`.
    """
    raw = await request.body()
    if not _autorizado(
        request, raw, x_webhook_signature, x_straton_signature, x_straton_timestamp
    ):
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError as extra:
        raise HTTPException(status_code=400, detail="JSON inválido") from extra

    evento = _evento(payload)
    dados = _dados(payload)

    # Idempotência da Straton: mesmo event_id não processa duas vezes.
    if x_straton_event_id:
        chave = f"straton:event:{x_straton_event_id}"
        if memory.get_lead(chave).get("done"):
            return {"status": "duplicado", "evento": evento, "event_id": x_straton_event_id}
        memory.save_lead(chave, {"done": True, "evento": evento})

    if _esta_pendente(payload):
        return _tratar_pendente(evento, dados)

    if _esta_expirado(payload):
        return _tratar_expirado(evento, dados)

    if not _esta_pago(payload):
        logger.info("Pagamento ignorado: evento=%s não é aprovação", evento)
        return {"status": "ignorado", "evento": evento}

    ref = _ref(payload)
    ig_id = ig_checkout.parse_ref(ref)
    if ig_id:
        try:
            ig_checkout.on_paid(ig_id, f"evento {evento}")
        except Exception:
            logger.exception("Liberar pack no Instagram falhou para %s", ig_id)
            memory.mark_paid(ig_id)
            alert.notify_confirmed(
                ig_id, f"pago na DM · MANDA O PACK NO INSTAGRAM (evento {evento})"
            )
        return {"status": "pago", "igsid": ig_id, "entrega": "instagram", "evento": evento}

    tg_id = telegram_sales.parse_ref(ref)
    if tg_id:
        tx = str(dados.get("transaction_id") or dados.get("id") or "")
        if tx:
            pedidos.mark_status(tx=tx, status="paid")
        try:
            telegram_sales.fulfill(tg_id)
        except Exception:
            logger.exception("Liberar Telegram falhou para %s", tg_id)
        alert.notify_confirmed(tg_id, f"pago no bot Telegram (evento {evento})")
        return {"status": "pago", "telegram_id": tg_id, "evento": evento}

    if not ref:
        logger.warning(
            "Pagamento aprovado sem referência do lead: evento=%s payload=%s",
            evento,
            json.dumps(payload)[:800],
        )
        # Ainda assim avisa se veio buyer_name da Straton.
        buyer = str(dados.get("buyer_name") or dados.get("customer", {}).get("name") or "")
        tx = str(dados.get("transaction_id") or dados.get("id") or "")
        if buyer or tx:
            alert.notify_confirmed(
                tx or "sem-ref",
                f"pago sem IGSID · {buyer} · evento {evento}",
            )
        return {"status": "sem_referencia", "evento": evento}

    memory.mark_paid(ref)
    logger.info("Pagamento confirmado para IGSID=%s via evento=%s", ref, evento)
    alert.notify_confirmed(ref, f"a plataforma confirmou o pagamento (evento {evento})")
    return {"status": "pago", "igsid": ref, "evento": evento}


def _tratar_pendente(evento: str, dados: dict) -> dict[str, Any]:
    tx = str(dados.get("transaction_id") or dados.get("id") or "")
    buyer = str(
        dados.get("buyer_name")
        or (dados.get("customer") or {}).get("name")
        or ""
    )
    amount = dados.get("amount_cents")
    try:
        amount_cents = int(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount_cents = None
    alert.notify_pix_status(
        "pix_pendente",
        buyer,
        tx or "sem-id",
        amount_cents,
        detalhe="PIX gerado. Cobra ele no bot agora antes de expirar.",
    )
    if tx:
        pedidos.mark_status(tx=tx, status="pending")
    nudge = pix_rmk.nudge(buyer, tx or "sem-id", "pending")
    tg_id = telegram_sales.parse_ref(str(dados.get("external_id") or ""))
    bot = None
    if tg_id:
        bot = telegram_sales.nudge_open_pix(tg_id, "pending")
    logger.info(
        "PIX pendente evento=%s buyer=%s tx=%s nudge=%s bot=%s",
        evento,
        buyer,
        tx,
        nudge,
        bot,
    )
    return {
        "status": "pendente",
        "evento": evento,
        "transaction_id": tx,
        "buyer": buyer,
        "nudge": nudge,
    }


def _tratar_expirado(evento: str, dados: dict) -> dict[str, Any]:
    tx = str(dados.get("transaction_id") or dados.get("id") or "")
    buyer = str(
        dados.get("buyer_name")
        or (dados.get("customer") or {}).get("name")
        or ""
    )
    amount = dados.get("amount_cents")
    try:
        amount_cents = int(amount) if amount is not None else None
    except (TypeError, ValueError):
        amount_cents = None
    alert.notify_pix_status(
        "pix_expirou",
        buyer,
        tx or "sem-id",
        amount_cents,
        detalhe="PIX expirou sem pagar. Manda gerar de novo no bot.",
    )
    if tx:
        pedidos.mark_status(tx=tx, status="expired")
    nudge = pix_rmk.nudge(buyer, tx or "sem-id", "expired")
    tg_id = telegram_sales.parse_ref(str(dados.get("external_id") or ""))
    bot = None
    if tg_id:
        bot = telegram_sales.nudge_open_pix(tg_id, "expired")
    logger.info(
        "PIX expirado evento=%s buyer=%s tx=%s nudge=%s bot=%s",
        evento,
        buyer,
        tx,
        nudge,
        bot,
    )
    return {
        "status": "expirado",
        "evento": evento,
        "transaction_id": tx,
        "buyer": buyer,
        "nudge": nudge,
    }


def _autorizado(
    request: Request,
    raw: bytes,
    assinatura: str | None,
    straton_sig: str | None,
    straton_ts: str | None,
) -> bool:
    settings = get_settings()
    segredo_straton = settings.straton_webhook_secret or settings.payment_webhook_secret
    if straton_sig and straton_ts and segredo_straton:
        try:
            if abs(time.time() - int(straton_ts)) <= 300:
                esperado = hmac.new(
                    segredo_straton.encode(),
                    f"{straton_ts}.{raw.decode('utf-8')}".encode(),
                    hashlib.sha256,
                ).hexdigest()
                if hmac.compare_digest(straton_sig, esperado):
                    return True
        except (ValueError, UnicodeDecodeError):
            logger.warning("Assinatura Straton malformada")

    segredo = settings.payment_webhook_secret
    if not segredo and not segredo_straton:
        logger.error("PAYMENT_WEBHOOK_SECRET não configurado; recusando o webhook")
        return False
    segredo = segredo or segredo_straton

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


def _dados(payload: dict) -> dict:
    dados = payload.get("data")
    return dados if isinstance(dados, dict) else payload


def _esta_pago(payload: dict) -> bool:
    dados = _dados(payload)
    candidatos = [
        payload.get("event"),
        payload.get("type"),
        payload.get("event_type"),
        payload.get("status"),
        dados.get("event"),
        dados.get("status"),
        dados.get("type"),
    ]
    return any(
        isinstance(v, str) and v.strip().lower() in _APROVADO for v in candidatos
    )


def _esta_pendente(payload: dict) -> bool:
    evento = _evento(payload).strip().lower()
    if evento in _APROVADO or evento in _EXPIRADO:
        return False
    dados = _dados(payload)
    candidatos = [
        payload.get("event"),
        payload.get("type"),
        payload.get("event_type"),
        dados.get("event"),
        dados.get("status"),
    ]
    return any(
        isinstance(v, str) and v.strip().lower() in _PENDENTE for v in candidatos
    )


def _esta_expirado(payload: dict) -> bool:
    evento = _evento(payload).strip().lower()
    if evento in _APROVADO:
        return False
    dados = _dados(payload)
    candidatos = [
        payload.get("event"),
        payload.get("type"),
        payload.get("event_type"),
        dados.get("event"),
        dados.get("status"),
    ]
    return any(
        isinstance(v, str) and v.strip().lower() in _EXPIRADO for v in candidatos
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
            if telegram_sales.parse_ref(candidato) or ig_checkout.parse_ref(candidato):
                return candidato
            # IGSID é numérico e longo. Qualquer outra coisa não é o nosso lead.
            if candidato.isdigit() and len(candidato) >= 8:
                return candidato
            logger.info("Referência %r ignorada: não parece um IGSID", candidato[:60])
    return None
