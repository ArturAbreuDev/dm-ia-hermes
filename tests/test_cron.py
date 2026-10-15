from app.config import get_settings
from app.main import app
from app.services import cronjobs
from fastapi.testclient import TestClient

client = TestClient(app)


def test_cron_rmk_recusa_sem_segredo(monkeypatch) -> None:
    monkeypatch.setenv("CRON_SECRET", "segredo-cron-teste")
    monkeypatch.setenv("DIARY_PASSWORD", "outra")
    get_settings.cache_clear()
    r = client.get("/v1/cron/rmk")
    assert r.status_code == 403


def test_cron_rmk_aceita_header_vercel(monkeypatch) -> None:
    monkeypatch.setenv("CRON_SECRET", "segredo-cron-teste")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.telegram_sales.process_due",
        lambda limit=20: {"due": 0, "resultados": []},
    )
    r = client.get("/v1/cron/rmk", headers={"x-vercel-cron": "1"})
    assert r.status_code == 200
    assert r.json()["due"] == 0


def test_cron_rmk_aceita_senha_do_diario(monkeypatch) -> None:
    monkeypatch.setenv("CRON_SECRET", "segredo-cron-teste")
    monkeypatch.setenv("DIARY_PASSWORD", "senha-diario")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.telegram_sales.process_due",
        lambda limit=20: {"due": 1, "resultados": []},
    )
    r = client.get(
        "/v1/cron/rmk", headers={"Authorization": "Bearer senha-diario"}
    )
    assert r.status_code == 200
    assert r.json()["due"] == 1


def test_ensure_cria_job_rmk(monkeypatch) -> None:
    monkeypatch.setenv("CRONJOBS_API_KEY", "chave-teste")
    monkeypatch.setenv("DIARY_PASSWORD", "senha-diario")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://dm-ia-hermes.vercel.app")
    get_settings.cache_clear()
    pedidos: list[tuple] = []

    class Fake:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **k):
            pedidos.append(("GET", url))
            return type(
                "R",
                (),
                {"raise_for_status": lambda self=None: None, "json": lambda self=None: {"jobs": []}},
            )()

        def put(self, url, **k):
            pedidos.append(("PUT", url, k.get("json")))
            return type(
                "R",
                (),
                {
                    "raise_for_status": lambda self=None: None,
                    "json": lambda self=None: {"jobId": 99},
                },
            )()

        def patch(self, url, **k):
            pedidos.append(("PATCH", url))
            return type("R", (), {"raise_for_status": lambda self=None: None})()

    monkeypatch.setattr(cronjobs.httpx, "Client", lambda **k: Fake())
    out = cronjobs.ensure()
    assert out["ok"] is True
    titulos = {j["title"] for j in out["jobs"]}
    assert "hermes-rmk" in titulos
    assert "hermes-previas-semana" in titulos
    assert any(p[0] == "PUT" for p in pedidos)
    corpo = next(p[2] for p in pedidos if p[0] == "PUT")
    job = corpo["job"]
    assert job["url"].endswith("/v1/cron/rmk")
    assert job["schedule"]["minutes"] == list(range(0, 60, 5))
    assert job["extendedData"]["headers"]["Authorization"] == "Bearer senha-diario"
    assert job["extendedData"]["headers"]["X-Cron-Secret"] == "senha-diario"
