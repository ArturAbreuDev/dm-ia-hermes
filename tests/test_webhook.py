from __future__ import annotations

import hashlib
import hmac
import json
import os

os.environ["APP_ENV"] = "test"
os.environ["META_VERIFY_TOKEN"] = "test-token"
os.environ["WEBHOOK_VERIFY_TOKEN"] = "test-token"
os.environ["META_APP_SECRET"] = "test-secret"
os.environ["OPENAI_API_KEY"] = ""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.sales_agent import _clean, wants_human

get_settings.cache_clear()
client = TestClient(app)


def test_health() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_webhook_verification() -> None:
    response = client.get(
        "/api/instagram/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-token",
            "hub.challenge": "12345",
        },
    )
    assert response.status_code == 200
    assert response.text == "12345"


def test_legacy_webhook_path_still_verifies() -> None:
    response = client.get(
        "/webhooks/instagram",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-token",
            "hub.challenge": "12345",
        },
    )
    assert response.status_code == 200
    assert response.text == "12345"


def test_webhook_rejects_bad_signature() -> None:
    response = client.post(
        "/api/instagram/webhook",
        content=b'{"object":"instagram","entry":[]}',
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert response.status_code == 403


def test_webhook_accepts_valid_signature() -> None:
    body = json.dumps(
        {
            "object": "instagram",
            "entry": [],
        }
    ).encode()
    digest = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    response = client.post(
        "/api/instagram/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={digest}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_no_reply_marker_silences_the_bot() -> None:
    assert _clean("[NO_REPLY]") == ""


def test_clean_strips_prefix_and_quotes() -> None:
    assert _clean('Resposta: "kkkk que foi? 😂"') == "kkkk que foi? 😂"


def test_wants_human_is_off_without_keywords() -> None:
    get_settings.cache_clear()
    assert not wants_human("quero falar com um atendente")


def test_telegram_requires_token(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    monkeypatch.setattr(settings, "telegram_default_chat_id", "")
    response = client.post(
        "/v1/telegram/messages",
        json={"to": "Artur", "text": "oi"},
    )
    assert response.status_code == 400
