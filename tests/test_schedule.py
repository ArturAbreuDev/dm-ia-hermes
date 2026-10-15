"""Storage de mídia + fila de agendamento (sem Meta)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.services import scheduler
from app.store import schedule, uploads


def test_upload_salva_e_serve(monkeypatch) -> None:
    monkeypatch.setattr(uploads, "_postgres_dsn", lambda: None)
    monkeypatch.setattr(uploads, "_put_vercel_blob", lambda *a, **k: None)
    local: dict = {}
    monkeypatch.setattr(uploads, "_local", local)
    monkeypatch.setattr(uploads, "_sqlite", _fail_sqlite)

    salvo = uploads.save(b"fake-jpeg-bytes", "image/jpeg", "foto.jpg")
    assert salvo["id"]
    assert salvo["via"] == "neon"
    assert "/media/uploads/" in salvo["url"]
    assert salvo["id"] in local

    got = uploads.get_bytes(salvo["id"])
    assert got is not None
    data, mime = got
    assert data == b"fake-jpeg-bytes"
    assert mime == "image/jpeg"


def test_upload_rejeita_grande(monkeypatch) -> None:
    monkeypatch.setattr(uploads, "_put_vercel_blob", lambda *a, **k: None)
    try:
        uploads.save(b"x" * (uploads.MAX_BYTES + 1), "video/mp4", "gordo.mp4")
        assert False, "deveria rejeitar"
    except ValueError as erro:
        assert "MB" in str(erro)


def test_agenda_e_processa_due(monkeypatch) -> None:
    monkeypatch.setattr(schedule, "_postgres_dsn", lambda: None)
    # Isola o SQLite em memória pra não sujar o arquivo do projeto.
    import sqlite3
    from contextlib import contextmanager

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    @contextmanager
    def fake_sqlite():
        yield conn
        conn.commit()

    monkeypatch.setattr(schedule, "_sqlite", fake_sqlite)

    passado = datetime.now(timezone.utc) - timedelta(minutes=1)
    item = schedule.create(
        kind="story",
        media_url="https://example.com/a.jpg",
        scheduled_for=passado,
    )
    assert item["status"] == "pending"
    assert schedule.due()

    fake = MagicMock()
    fake.media_id = "ig_123"
    monkeypatch.setattr(
        "app.services.publish.publish",
        lambda *a, **k: fake,
    )
    out = scheduler.process_due()
    assert out["due"] == 1
    assert out["resultados"][0]["ok"] is True
    assert schedule.get(item["id"])["status"] == "published"


def test_cancela_pendente(monkeypatch) -> None:
    monkeypatch.setattr(schedule, "_postgres_dsn", lambda: None)
    import sqlite3
    from contextlib import contextmanager

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    @contextmanager
    def fake_sqlite():
        yield conn
        conn.commit()

    monkeypatch.setattr(schedule, "_sqlite", fake_sqlite)

    futuro = datetime.now(timezone.utc) + timedelta(hours=2)
    item = schedule.create(
        kind="feed",
        media_url="https://example.com/b.jpg",
        caption="oi",
        scheduled_for=futuro,
    )
    assert schedule.cancel(item["id"]) is True
    assert schedule.get(item["id"])["status"] == "cancelled"
    assert schedule.due() == []


def _fail_sqlite():
    raise RuntimeError("sem sqlite neste teste")
