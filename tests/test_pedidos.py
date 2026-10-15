from app.config import get_settings
from app.main import app
from app.store import pedidos
from fastapi.testclient import TestClient


def _sqlite_mem(monkeypatch):
    import sqlite3
    from contextlib import contextmanager

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    @contextmanager
    def fake():
        yield conn
        conn.commit()

    monkeypatch.setattr(pedidos, "_postgres_dsn", lambda: None)
    monkeypatch.setattr(pedidos, "_sqlite", fake)
    return conn


def test_grava_e_lista_nome(monkeypatch) -> None:
    _sqlite_mem(monkeypatch)
    pedidos.save(
        user_id="11",
        nome="Rogerio Nunes De Alcantara",
        username="rogerio",
        status="pending",
        amount="24,90",
        tx="abc",
        pedido_id="tx:abc",
    )
    itens = pedidos.listar()
    assert itens[0]["nome"] == "Rogerio Nunes De Alcantara"
    assert itens[0]["username"] == "rogerio"
    pedidos.mark_status(tx="abc", status="paid")
    assert pedidos.listar()[0]["status"] == "paid"


def test_pagina_pedidos(monkeypatch) -> None:
    monkeypatch.setenv("DIARY_PASSWORD", "segredo")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.api.pedidos.pedidos.listar",
        lambda limit=120: [
            {
                "nome": "big smoke",
                "username": "bigsmoke0808",
                "user_id": "22",
                "produto": "Acesso VIP",
                "origem": "telegram",
                "amount": "24,90",
                "status": "start",
                "created_at": "2026-10-09T12:00:00+00:00",
            }
        ],
    )
    r = TestClient(app).get("/pedidos?k=segredo")
    assert r.status_code == 200
    assert "big smoke" in r.text
    assert "@bigsmoke0808" in r.text
    get_settings.cache_clear()
