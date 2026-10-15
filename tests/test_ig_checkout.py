from app.services import engagement, ig_checkout
from app.store import memory


def test_reconhece_sem_telegram() -> None:
    for frase in [
        "nao tenho telegram",
        "não uso telegram",
        "sem telegram",
        "manda no insta",
        "manda aqui",
        "só no instagram",
        "pode mandar no chat",
    ]:
        assert "sem_telegram" in engagement.read_flags(frase), frase
        assert not engagement.decide({}, frase, False).silent, frase


def test_parse_ref_ig() -> None:
    assert ig_checkout.parse_ref("hermes:ig:12655:abc") == "12655"
    assert ig_checkout.parse_ref("hermes:tg:555:abc") is None
    assert ig_checkout.parse_ref("") is None


def test_enviar_pix_grava_codigo(monkeypatch) -> None:
    igsid = "ig-pix-teste"
    memory.save_lead(igsid, {})
    monkeypatch.setattr(
        ig_checkout.straton,
        "create_cashin",
        lambda **k: {"pix_code": "00020126TESTE", "id": "tx-1", "qr_code": ""},
    )
    monkeypatch.setattr(ig_checkout.instagram, "send_image_message", lambda *a, **k: {})
    texto = ig_checkout.enviar_pix(igsid, "Bruno")
    assert "00020126TESTE" not in texto
    assert "/pix/" in texto
    assert "pack" in texto.lower()
    lead = memory.get_lead(igsid)
    assert lead.get("pix_ig_code") == "00020126TESTE"
    assert lead.get("pix_ig_slug")
    assert lead.get("entrega") == "instagram"
    monkeypatch.setattr(
        ig_checkout.straton,
        "create_cashin",
        lambda **k: (_ for _ in ()).throw(AssertionError("não deveria criar de novo")),
    )
    de_novo = ig_checkout.enviar_pix(igsid, "Bruno")
    assert lead["pix_ig_slug"] in de_novo
    from fastapi.testclient import TestClient
    from app.main import app

    r = TestClient(app).get(f"/pix/{lead['pix_ig_slug']}")
    assert r.status_code == 200
    assert "00020126TESTE" in r.text


def test_enviar_pix_usa_link_da_straton(monkeypatch) -> None:
    igsid = "ig-pix-hosted"
    memory.save_lead(igsid, {})
    monkeypatch.setattr(
        ig_checkout.straton,
        "create_cashin",
        lambda **k: {
            "pix_code": "00020126HOST",
            "id": "tx-2",
            "payment_url": "https://stratonbot.app/pay/abc",
        },
    )
    monkeypatch.setattr(ig_checkout.instagram, "send_image_message", lambda *a, **k: {})
    texto = ig_checkout.enviar_pix(igsid, "Leo")
    assert "https://stratonbot.app/pay/abc" in texto
    assert "/pix/" not in texto


def test_webhook_pago_ig_chama_entrega(monkeypatch) -> None:
    vistos = []
    monkeypatch.setattr(
        "app.services.ig_checkout.on_paid",
        lambda igsid, detalhe="": vistos.append(igsid) or {"aviso": True},
    )
    from tests.test_straton_webhook import _straton

    out = _straton(
        {
            "event": "cashin.paid",
            "event_id": f"evt-ig-pack-{__import__('uuid').uuid4().hex}",
            "data": {
                "id": "tx-ig-1",
                "status": "paid",
                "external_id": "hermes:ig:999888:abcdef",
                "buyer_name": "Rafa",
            },
        },
        monkeypatch,
    )
    assert out["status"] == "pago"
    assert out["igsid"] == "999888"
    assert out["entrega"] == "instagram"
    assert vistos == ["999888"]
