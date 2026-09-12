from app.config import get_settings
from app.main import app
from app.services import engagement
from app.store import memory
from fastapi.testclient import TestClient

IGSID = "932195672781138"
client = TestClient(app)


def test_silenciado_nao_recebe_resposta() -> None:
    for frase in ["oi", "bom dia", "vc é linda", "responde ai", "tá me ignorando?"]:
        stance = engagement.decide({"muted": True}, frase, paid=False)
        assert stance.silent, frase
        assert stance.reason == "silenciado_manualmente"


def test_falar_de_comprar_fura_o_silencio() -> None:
    for frase in [
        "vou pagar agora",
        "quero comprar",
        "vou assinar",
        "me manda o link",
        "quanto custa?",
        "qual o valor?",
        "como pago?",
        "tô dentro",
        "fechou",
        "vou fazer o pix",
        "paguei",
        "fiz o pix",
    ]:
        assert not engagement.decide({"muted": True}, frase, paid=False).silent, frase


def test_erro_de_pagamento_tambem_fura() -> None:
    stance = engagement.decide({"muted": True}, "o pix deu erro", paid=False)
    assert not stance.silent


def test_papo_solto_nao_conta_como_intencao() -> None:
    for frase in ["oi tudo bem", "vc grava com fã?", "me manda uma foto", "kkkk"]:
        assert not engagement.wants_to_buy(frase), frase


def test_rotas_de_lead_exigem_a_chave(monkeypatch) -> None:
    monkeypatch.setenv("DIARY_PASSWORD", "senha-de-teste")
    get_settings.cache_clear()

    assert client.post(f"/v1/leads/{IGSID}/mute").status_code == 403
    assert client.post(f"/v1/leads/{IGSID}/mute?k=errada").status_code == 403

    ok = client.post(f"/v1/leads/{IGSID}/mute?k=senha-de-teste")
    assert ok.status_code == 200
    assert ok.json()["lead"]["muted"] is True

    desfaz = client.delete(f"/v1/leads/{IGSID}/mute?k=senha-de-teste")
    assert "muted" not in desfaz.json()["lead"]
    memory.set_muted(IGSID, False)
