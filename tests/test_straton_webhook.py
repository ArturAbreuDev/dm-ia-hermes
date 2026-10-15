"""Testes do webhook Straton: pending, paid, expired."""

import hashlib
import hmac
import json
import time
import uuid

from app.config import get_settings
from app.main import app
from app.store import memory
from fastapi.testclient import TestClient

SEGREDO = "segredo-straton-teste"
client = TestClient(app)


def _configurar(monkeypatch) -> None:
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", SEGREDO)
    monkeypatch.setenv("STRATON_WEBHOOK_SECRET", SEGREDO)
    get_settings.cache_clear()


def _straton(payload: dict, monkeypatch) -> dict:
    _configurar(monkeypatch)
    corpo = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = hmac.new(
        SEGREDO.encode(), f"{ts}.{corpo.decode()}".encode(), hashlib.sha256
    ).hexdigest()
    return client.post(
        "/v1/payments/webhook",
        content=corpo,
        headers={
            "Content-Type": "application/json",
            "X-StratonBot-Signature": sig,
            "X-StratonBot-Timestamp": ts,
            "X-StratonBot-Event-Id": payload.get("event_id")
            or f"evt-{time.time()}-{id(payload)}",
        },
    ).json()


def test_cashin_pending_avisa(monkeypatch) -> None:
    monkeypatch.setattr("app.services.alert.notify_pix_status", lambda *a, **k: True)
    out = _straton(
        {
            "event": "cashin.pending",
            "event_id": f"evt-pending-{uuid.uuid4().hex}",
            "data": {
                "transaction_id": "tx-pend-1",
                "buyer_name": "Jenerson",
                "amount_cents": 2490,
                "status": "pending",
            },
        },
        monkeypatch,
    )
    assert out["status"] == "pendente"
    assert out["buyer"] == "Jenerson"


def test_cashin_expired_avisa(monkeypatch) -> None:
    monkeypatch.setattr("app.services.alert.notify_pix_status", lambda *a, **k: True)
    out = _straton(
        {
            "event": "cashin.expired",
            "event_id": f"evt-exp-{uuid.uuid4().hex}",
            "data": {
                "transaction_id": "tx-exp-1",
                "buyer_name": "Guilherme",
                "amount_cents": 2490,
                "status": "expired",
            },
        },
        monkeypatch,
    )
    assert out["status"] == "expirado"


def test_cashin_paid_marca_igsid(monkeypatch) -> None:
    igsid = "1265546675660956"
    memory.clear_paid(igsid)
    monkeypatch.setattr("app.services.alert.notify_confirmed", lambda *a, **k: True)
    out = _straton(
        {
            "event": "cashin.paid",
            "event_id": f"evt-paid-{uuid.uuid4().hex}",
            "data": {
                "id": "tx-paid-1",
                "status": "paid",
                "external_id": igsid,
                "buyer_name": "Gaucho",
            },
        },
        monkeypatch,
    )
    assert out["status"] == "pago"
    assert memory.is_paid(igsid)
    memory.clear_paid(igsid)


def test_cashin_paid_libera_telegram(monkeypatch) -> None:
    vistos = []
    monkeypatch.setattr(
        "app.services.telegram_sales.fulfill",
        lambda uid: vistos.append(uid) or "liberado",
    )
    monkeypatch.setattr("app.services.alert.notify_confirmed", lambda *a, **k: True)
    out = _straton(
        {
            "event": "cashin.paid",
            "event_id": f"evt-paid-tg-{uuid.uuid4().hex}",
            "data": {
                "id": "tx-paid-tg-1",
                "status": "paid",
                "external_id": "hermes:tg:555:abcdef",
                "buyer_name": "Leo",
            },
        },
        monkeypatch,
    )
    assert out["status"] == "pago"
    assert out["telegram_id"] == "555"
    assert vistos == ["555"]


def test_evento_duplicado_nao_reprocessa(monkeypatch) -> None:
    monkeypatch.setattr("app.services.alert.notify_pix_status", lambda *a, **k: True)
    payload = {
        "event": "cashin.pending",
        "event_id": f"evt-dup-{uuid.uuid4().hex}",
        "data": {"transaction_id": "tx-dup", "buyer_name": "X", "amount_cents": 100},
    }
    assert _straton(payload, monkeypatch)["status"] == "pendente"
    assert _straton(payload, monkeypatch)["status"] == "duplicado"
