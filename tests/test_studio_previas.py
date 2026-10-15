from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import previews


def test_pagina_publicar_mostra_canal_e_videos(monkeypatch) -> None:
    monkeypatch.setenv("DIARY_PASSWORD", "segredo")
    get_settings.cache_clear()
    monkeypatch.setattr(
        previews,
        "painel_itens",
        lambda: [
            {
                "id": "r1",
                "kind": "vídeo",
                "url": "https://cdn.example/a.mp4",
                "caption": "prévia\nhttps://t.me/liviagommes_bot",
            }
        ],
    )
    monkeypatch.setattr(previews, "chat_id", lambda: "")
    monkeypatch.setattr(
        previews,
        "status",
        lambda: {"ok": "", "texto": "ainda não ligado", "titulo": "", "id": ""},
    )
    monkeypatch.setattr("app.api.studio.scheduler.process_due", lambda: {})
    html = TestClient(app).get("/publicar", params={"k": "segredo"}).text
    assert "Canal de prévias" in html
    assert "cdn.example/a.mp4" in html
    assert "t.me/liviagommes_bot" in html
    assert "Publicar esta no canal" in html
    assert "Publicar todas as prévias agora" in html
    assert "/publicar/ligar-previas" in html
    get_settings.cache_clear()
