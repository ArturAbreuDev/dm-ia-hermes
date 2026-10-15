import hashlib
import hmac
import json

from app.config import get_settings
from app.main import app
from app.store import memory
from fastapi.testclient import TestClient

SEGREDO = get_settings().payment_webhook_secret or "segredo-de-teste"
IGSID = "1265546675660956"
client = TestClient(app)


def _mandar(payload, *, query="", assinar=False):
    corpo = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if assinar:
        headers["X-Webhook-Signature"] = hmac.new(
            SEGREDO.encode(), corpo, hashlib.sha256
        ).hexdigest()
    url = "/v1/payments/webhook"
    if query:
        url += f"?{query}"
    return client.post(url, content=corpo, headers=headers)


def _limpar():
    memory.clear_paid(IGSID)


def test_recusa_sem_segredo(monkeypatch) -> None:
    """Endpoint aberto marcaria qualquer um como pago. Tem que fechar."""
    monkeypatch.setattr(get_settings(), "payment_webhook_secret", "", raising=False)
    get_settings.cache_clear()
    resposta = _mandar({"event": "SALE_APPROVED"})
    assert resposta.status_code == 403


def test_kirvano_marca_como_pago(monkeypatch) -> None:
    _configurar(monkeypatch)
    _limpar()
    resposta = _mandar(
        {"event": "SALE_APPROVED", "utm": {"src": IGSID}},
        query=f"secret={SEGREDO}",
    )
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "pago"
    assert memory.is_paid(IGSID)


def test_abacatepay_com_assinatura(monkeypatch) -> None:
    _configurar(monkeypatch)
    _limpar()
    resposta = _mandar(
        {"event": "checkout.completed", "data": {"externalId": IGSID}}, assinar=True
    )
    assert resposta.json()["status"] == "pago"
    assert memory.is_paid(IGSID)


def test_cakto_com_segredo_no_corpo(monkeypatch) -> None:
    _configurar(monkeypatch)
    _limpar()
    resposta = _mandar(
        {
            "secret": SEGREDO,
            "event": "purchase_approved",
            "data": {"metadata": {"ref": IGSID}},
        }
    )
    assert resposta.json()["status"] == "pago"
    assert memory.is_paid(IGSID)


def test_evento_que_nao_e_aprovacao_nao_marca(monkeypatch) -> None:
    _configurar(monkeypatch)
    _limpar()
    resposta = _mandar(
        {"event": "SALE_REFUSED", "utm": {"src": IGSID}}, query=f"secret={SEGREDO}"
    )
    assert resposta.json()["status"] == "ignorado"
    assert not memory.is_paid(IGSID)


def test_venda_sem_referencia_nao_marca_ninguem(monkeypatch) -> None:
    _configurar(monkeypatch)
    resposta = _mandar(
        {"event": "SALE_APPROVED", "customer": {"email": "x@y.com"}},
        query=f"secret={SEGREDO}",
    )
    assert resposta.json()["status"] == "sem_referencia"


def test_email_no_lugar_do_igsid_nao_vira_lead(monkeypatch) -> None:
    """Referência que não é IGSID não pode marcar um lead qualquer."""
    _configurar(monkeypatch)
    resposta = _mandar(
        {"event": "SALE_APPROVED", "utm": {"src": "joao@email.com"}},
        query=f"secret={SEGREDO}",
    )
    assert resposta.json()["status"] == "sem_referencia"


def test_segredo_errado_e_recusado(monkeypatch) -> None:
    _configurar(monkeypatch)
    assert _mandar({"event": "SALE_APPROVED"}, query="secret=errado").status_code == 403


def test_link_leva_a_marca_do_lead(monkeypatch) -> None:
    # Só o Botgram aceita query string; o da Straton é t.me e fica limpo.
    # A escolha no /diario (banco) manda mais que a env, então força Botgram.
    from app.store import runtime

    runtime.set("checkout_provider", "botgram")
    monkeypatch.setenv("CHECKOUT_REF_PARAM", "src")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.checkout_link(IGSID).endswith(f"src={IGSID}")
    # Sem o parâmetro configurado o link fica limpo, como está hoje.
    monkeypatch.delenv("CHECKOUT_REF_PARAM", raising=False)
    get_settings.cache_clear()
    assert get_settings().checkout_link(IGSID) == get_settings().active_checkout_url()
    runtime.set("checkout_provider", "straton")
    get_settings.cache_clear()


def _configurar(monkeypatch) -> None:
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", SEGREDO)
    get_settings.cache_clear()
