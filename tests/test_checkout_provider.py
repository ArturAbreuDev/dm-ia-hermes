"""Troca de checkout pelo /diario, sem redeploy."""

from app.config import get_settings
from app.store import runtime


def test_padrao_e_straton(monkeypatch) -> None:
    monkeypatch.delenv("CHECKOUT_DEFAULT", raising=False)
    runtime.set("checkout_provider", "straton")
    get_settings.cache_clear()
    s = get_settings()
    assert s.checkout_provider() == "straton"
    url = s.active_checkout_url()
    assert "t.me/" in url or url.endswith("/vip")
    assert s.active_price() == "24,90"


def test_troca_para_botgram() -> None:
    runtime.set("checkout_provider", "botgram")
    get_settings.cache_clear()
    s = get_settings()
    assert s.checkout_provider() == "botgram"
    assert "botgram.club" in s.active_checkout_url()
    assert "19,90" in s.active_price()
    runtime.set("checkout_provider", "straton")
    get_settings.cache_clear()


def test_vip_abre_o_bot_nosso() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    runtime.set("checkout_provider", "straton")
    get_settings.cache_clear()
    s = get_settings()
    assert s.telegram_vip_bot() == "liviagommes_bot"
    html = TestClient(app).get("/vip").text
    assert "t.me/liviagommes_bot" in html
    assert "liviagomesvip_bot" not in html
    assert "CANAL VIP" in html
    assert "Para quem não tem Telegram" not in html
    assert "Para quem não tem Instagram" not in html
    assert "Descobriu meu segredinho" in html
    assert TestClient(app).get("/links").status_code == 200


def test_linktree_salva_botao(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.store import linktree

    monkeypatch.setenv("DIARY_PASSWORD", "segredo")
    get_settings.cache_clear()
    caixa: dict[str, str] = {}
    monkeypatch.setattr("app.store.runtime.get", lambda k: caixa.get(k))
    monkeypatch.setattr(
        "app.store.runtime.set", lambda k, v: caixa.update({k: v})
    )
    client = TestClient(app)
    r = client.post(
        "/linktree",
        data={
            "k": "segredo",
            "tagline": "oi",
            "instagram": "livia",
            "titulo": ["Privacy"],
            "desc": ["lá"],
            "url": ["https://privacy.com.br/x"],
            "kind": ["privacy"],
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    html = client.get("/vip").text
    assert "Privacy" in html
    assert "https://privacy.com.br/x" in html
    assert "Para quem não tem Telegram" not in html
    assert linktree.carregar()["instagram"] == "livia"
    get_settings.cache_clear()
