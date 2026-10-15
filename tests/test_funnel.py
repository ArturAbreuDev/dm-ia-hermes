import json

from app.services import funnel
from app.store import uploads


def test_default_tem_esperas_e_rmk(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    gaps = funnel.rmk_gaps_hours()
    assert len(gaps) == 3
    assert abs(gaps[0] - 0.25) < 0.01
    assert abs(gaps[1] - 3) < 0.01
    assert abs(gaps[2] - 24) < 0.01
    passos = funnel.rmk_steps()
    assert all(p["text"] for p in passos)
    assert passos[-1]["loop"] is True
    assert passos[-1]["loop_minutes"] == 1440
    banner = funnel.banner()
    assert banner["name"]
    assert banner["short"]
    assert "VIP" in banner["text"] or "Start" in banner["text"]
    bloco = next(n for n in funnel.default_funnel()["nodes"] if n["type"] == "banner")
    start = next(n for n in funnel.default_funnel()["nodes"] if n["type"] == "start")
    assert bloco["data"]["label"] == "Perfil do bot"
    assert "photo_url" in bloco["data"]
    assert start["position"]["y"] > bloco["position"]["y"] + 400


def test_midias_previa_so_com_arquivo(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    assert funnel.midias_previa() == []
    monkeypatch.setattr(
        "app.services.funnel.start_payload",
        lambda: {
            "id": "start",
            "text": "start",
            "video_url": "https://cdn.example/s.mp4",
            "photo_url": "",
            "video_file_id": "",
            "photo_file_id": "",
        },
    )
    monkeypatch.setattr(
        "app.services.funnel.rmk_steps",
        lambda: [
            {
                "id": "r1",
                "text": "rmk",
                "video_url": "",
                "photo_url": "https://cdn.example/r.jpg",
                "video_file_id": "",
                "photo_file_id": "",
            },
            {
                "id": "r2",
                "text": "sem midia",
                "video_url": "",
                "photo_url": "",
                "video_file_id": "",
                "photo_file_id": "",
            },
        ],
    )
    ids = [i["id"] for i in funnel.midias_previa()]
    assert ids == ["start", "r1"]


def test_funil_antigo_ganha_banner(monkeypatch) -> None:
    antigo = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {"text": "oi"},
            }
        ],
        "edges": [],
    }
    monkeypatch.setattr(
        "app.services.funnel.runtime.get",
        lambda *_a, **_k: json.dumps(antigo),
    )
    dados = funnel.load()
    tipos = [n["type"] for n in dados["nodes"]]
    assert "banner" in tipos
    assert any(e["source"] == "banner" and e["target"] == "start" for e in dados["edges"])


def test_espera_customizada(monkeypatch) -> None:
    dados = funnel.default_funnel()
    for n in dados["nodes"]:
        if n["id"] == "r1":
            n["data"]["delay_minutes"] = 5
    monkeypatch.setattr(
        "app.services.funnel.runtime.get",
        lambda *_a, **_k: json.dumps(dados),
    )
    gaps = funnel.rmk_gaps_hours()
    assert abs(gaps[0] - 5 / 60) < 0.001
def test_anexa_foto_no_start(monkeypatch) -> None:
    dados = funnel.default_funnel()
    monkeypatch.setattr(
        "app.services.funnel.runtime.get",
        lambda *_a, **_k: json.dumps(dados),
    )
    gravados: list[str] = []
    monkeypatch.setattr(
        "app.services.funnel.runtime.set",
        lambda _k, v: gravados.append(v),
    )
    funnel.anexar_midia("start", "video_url", "https://cdn.example/v.mp4")
    assert gravados
    salvo = json.loads(gravados[-1])
    start = next(n for n in salvo["nodes"] if n["id"] == "start")
    assert start["data"]["video_url"] == "https://cdn.example/v.mp4"


def test_salvar_textos_nao_apaga_video(monkeypatch) -> None:
    estado = {"v": json.dumps(funnel.default_funnel())}
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: estado["v"])
    monkeypatch.setattr(
        "app.services.funnel.runtime.set",
        lambda _k, v: estado.__setitem__("v", v),
    )
    funnel.anexar_midia("start", "video_url", "https://x.blob.vercel-storage.com/v.mp4")
    dados = json.loads(estado["v"])
    for n in dados["nodes"]:
        if n["id"] == "start":
            n["data"]["video_url"] = ""
            n["data"]["text"] = "texto novo"
    funnel.save(dados)
    start = next(n for n in json.loads(estado["v"])["nodes"] if n["id"] == "start")
    assert "blob.vercel-storage.com" in start["data"]["video_url"]
    assert start["data"]["text"] == "texto novo"


def test_anexa_foto_no_banner(monkeypatch) -> None:
    dados = funnel.default_funnel()
    estado = {"v": json.dumps(dados)}
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: estado["v"])
    monkeypatch.setattr(
        "app.services.funnel.runtime.set",
        lambda _k, v: estado.__setitem__("v", v),
    )
    funnel.anexar_midia("banner", "photo_url", "https://x.blob.vercel-storage.com/b.jpg")
    banner = next(n for n in json.loads(estado["v"])["nodes"] if n["id"] == "banner")
    assert banner["data"]["photo_url"].endswith("b.jpg")


def test_salvar_textos_nao_apaga_foto_banner(monkeypatch) -> None:
    estado = {"v": json.dumps(funnel.default_funnel())}
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: estado["v"])
    monkeypatch.setattr(
        "app.services.funnel.runtime.set",
        lambda _k, v: estado.__setitem__("v", v),
    )
    funnel.anexar_midia("banner", "photo_url", "https://x.blob.vercel-storage.com/b.jpg")
    dados = json.loads(estado["v"])
    for n in dados["nodes"]:
        if n["id"] == "banner":
            n["data"]["photo_url"] = ""
            n["data"]["text"] = "novo recado do chat vazio"
    funnel.save(dados)
    banner = next(n for n in json.loads(estado["v"])["nodes"] if n["id"] == "banner")
    assert "blob.vercel-storage.com" in banner["data"]["photo_url"]
    assert banner["data"]["text"] == "novo recado do chat vazio"


def test_put_funil_publica_perfil(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    monkeypatch.setenv("DIARY_PASSWORD", "segredo")
    get_settings.cache_clear()
    estado = {"v": json.dumps(funnel.default_funnel())}
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: estado["v"])
    monkeypatch.setattr(
        "app.services.funnel.runtime.set",
        lambda _k, v: estado.__setitem__("v", v),
    )
    vistos: list = []
    monkeypatch.setattr(
        "app.api.funnel.telegram_sales.sync_profile",
        lambda **k: vistos.append(k) or {"foto": "ok", "description": "ok", "skipped": False},
    )
    client = TestClient(app)
    corpo = funnel.default_funnel()
    r = client.put("/v1/funil?k=segredo", json={"nodes": corpo["nodes"], "edges": corpo["edges"]})
    assert r.status_code == 200, r.text
    assert vistos
    assert r.json()["perfil"]["foto"] == "ok"
    get_settings.cache_clear()


def test_anexar_banner_publica_perfil(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    monkeypatch.setenv("DIARY_PASSWORD", "segredo")
    get_settings.cache_clear()
    estado = {"v": json.dumps(funnel.default_funnel())}
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: estado["v"])
    monkeypatch.setattr(
        "app.services.funnel.runtime.set",
        lambda _k, v: estado.__setitem__("v", v),
    )
    vistos: list = []
    monkeypatch.setattr(
        "app.api.funnel.telegram_sales.sync_profile",
        lambda **k: vistos.append(k) or {"foto": "ok", "skipped": False},
    )
    monkeypatch.setattr(
        "app.api.funnel.telegram_sales.cachear_na_telegram",
        lambda *a, **k: "FILEID",
    )
    client = TestClient(app)
    r = client.post(
        "/v1/funil/anexar?k=segredo",
        json={
            "node_id": "banner",
            "campo": "photo_url",
            "url": "https://x.blob.vercel-storage.com/b.jpg",
        },
    )
    assert r.status_code == 200, r.text
    assert vistos and vistos[0].get("force") is True
    banner = next(n for n in json.loads(estado["v"])["nodes"] if n["id"] == "banner")
    assert banner["data"]["photo_url"].endswith("b.jpg")
    assert banner["data"]["photo_file_id"] == "FILEID"
    get_settings.cache_clear()


def test_url_blob_aceita_upload_local() -> None:
    assert uploads.url_blob_publica("https://x.blob.vercel-storage.com/a.jpg")
    assert uploads.url_blob_publica("https://dm-ia-hermes.vercel.app/media/uploads/abc.jpg")
    assert not uploads.url_blob_publica("https://exemplo.com/foto.jpg")


def test_token_blob_tem_prefixo(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.store.uploads._blob_token",
        lambda: "vercel_blob_rw_storeid_secreto",
    )
    token = uploads.generate_client_token(pathname="funil/a.mp4")
    assert token.startswith("vercel_blob_client_storeid_")
