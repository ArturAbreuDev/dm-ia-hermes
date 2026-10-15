"""Remarketing e start do bot de Telegram."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.services import telegram_sales
from app.store import telegram_leads


def _sqlite_mem(monkeypatch):
    import sqlite3
    from contextlib import contextmanager

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    @contextmanager
    def fake():
        yield conn
        conn.commit()

    monkeypatch.setattr(telegram_leads, "_postgres_dsn", lambda: None)
    monkeypatch.setattr(telegram_leads, "_sqlite", fake)
    return conn


def test_start_agenda_rmk(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    enviados = []
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_photo",
        lambda *a, **k: enviados.append(("photo", k)),
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: enviados.append(("text", a, k)),
    )
    monkeypatch.setattr(telegram_sales, "COVER", MagicMock(exists=lambda: False))
    monkeypatch.setattr(telegram_sales, "_preco", lambda: "24,90")

    out = telegram_sales.handle_private_message(
        {
            "chat": {"type": "private", "id": 11},
            "from": {"id": 11, "first_name": "Bruno", "username": "bruno"},
            "text": "/start",
        }
    )
    assert out == "start"
    lead = telegram_leads.get("11")
    assert lead["status"] == "active"
    assert lead["rmk_step"] == 0
    assert enviados and enviados[0][0] == "text"


def test_start_com_mencao_do_bot(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    enviados = []
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: enviados.append(("text", a, k)),
    )
    monkeypatch.setattr(telegram_sales, "COVER", MagicMock(exists=lambda: False))
    monkeypatch.setattr(telegram_sales, "_preco", lambda: "24,90")
    out = telegram_sales.handle_private_message(
        {
            "chat": {"type": "private", "id": 12},
            "from": {"id": 12, "first_name": "Ana"},
            "text": "/start@liviagommes_bot",
        }
    )
    assert out == "start"
    assert enviados


def test_start_manda_video_pelo_file_id(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    enviados = []
    monkeypatch.setattr(
        telegram_sales.funnel,
        "start_payload",
        lambda: {
            "id": "start",
            "text": "oi",
            "video_url": "https://x.blob.vercel-storage.com/v.mp4",
            "photo_url": "",
            "video_file_id": "BAAD-VIDEO",
            "photo_file_id": "",
        },
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: enviados.append("text") or {},
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_video_url",
        lambda chat, video, **k: enviados.append(video) or {"video": {"file_id": video}},
    )
    monkeypatch.setattr(telegram_sales, "COVER", MagicMock(exists=lambda: False))
    monkeypatch.setattr(telegram_sales, "_preco", lambda: "24,90")
    out = telegram_sales.handle_private_message(
        {
            "chat": {"type": "private", "id": 14},
            "from": {"id": 14, "first_name": "Mia"},
            "text": "/start",
        }
    )
    assert out == "start"
    assert enviados == ["BAAD-VIDEO", "text"]


def test_start_video_depois_texto_sem_foto(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    ordem: list[str] = []
    monkeypatch.setattr(
        telegram_sales.funnel,
        "start_payload",
        lambda: {
            "id": "start",
            "text": "oi",
            "video_url": "https://x.blob.vercel-storage.com/v.mp4",
            "photo_url": "https://x.blob.vercel-storage.com/f.jpg",
            "video_file_id": "VID",
            "photo_file_id": "FOTO",
        },
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_video_url",
        lambda *a, **k: ordem.append("video") or {},
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_photo_url",
        lambda *a, **k: ordem.append("photo") or {},
    )
    markups: list[object] = []
    textos: list[str] = []
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: (
            textos.append(str(a[1]))
            or markups.append(k.get("reply_markup"))
            or ordem.append("text")
            or {}
        ),
    )
    monkeypatch.setattr(telegram_sales, "COVER", MagicMock(exists=lambda: False))
    monkeypatch.setattr(telegram_sales, "_preco", lambda: "24,90")
    out = telegram_sales.handle_private_message(
        {
            "chat": {"type": "private", "id": 15},
            "from": {"id": 15, "first_name": "Lia"},
            "text": "/start",
        }
    )
    assert out == "start"
    assert ordem == ["video", "text"]
    assert "photo" not in ordem
    assert textos and "oi" in textos[0]
    teclado = str(markups[-1])
    assert "pay_pix" in teclado
    assert "cartão" not in teclado.lower()
    assert "parar" not in teclado.lower()


def test_start_sem_capa_so_texto(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    capa = tmp_path / "cover.jpg"
    capa.write_bytes(b"\xff\xd8\xfffake")
    enviados: list[dict] = []
    monkeypatch.setattr(
        telegram_sales.funnel,
        "start_payload",
        lambda: {"text": "oi amor", "video_url": "", "photo_url": "", "video_file_id": "", "photo_file_id": ""},
    )
    monkeypatch.setattr(telegram_sales, "COVER", capa)
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_photo_bytes",
        lambda *a, **k: enviados.append({"foto": True}) or {},
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: enviados.append({"text": True, "body": a[1], "reply_markup": k.get("reply_markup")}),
    )
    monkeypatch.setattr(telegram_sales, "_preco", lambda: "24,90")
    out = telegram_sales.handle_private_message(
        {
            "chat": {"type": "private", "id": 16},
            "from": {"id": 16, "first_name": "Lia"},
            "text": "/start",
        }
    )
    assert out == "start"
    assert not any(item.get("foto") for item in enviados if isinstance(item, dict))
    assert any("oi amor" in str(item.get("body") or "") for item in enviados if isinstance(item, dict))
    teclado = str(next(item.get("reply_markup") for item in enviados if item.get("reply_markup")))
    assert "pay_pix" in teclado
    assert "cartão" not in teclado.lower()
    assert "parar" not in teclado.lower()


def test_start_cai_no_texto_se_video_quebra(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    enviados = []
    monkeypatch.setattr(
        telegram_sales.funnel,
        "start_payload",
        lambda: {"text": "oi", "video_url": "https://exemplo.com/v.mp4", "photo_url": ""},
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_video_url",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("failed to get HTTP URL content")),
    )
    monkeypatch.setattr(telegram_sales, "_baixar_midia", lambda *a, **k: None)
    monkeypatch.setattr(telegram_sales, "COVER", MagicMock(exists=lambda: False))
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: enviados.append(a[1]),
    )
    monkeypatch.setattr(telegram_sales, "_preco", lambda: "24,90")
    out = telegram_sales.handle_private_message(
        {
            "chat": {"type": "private", "id": 13},
            "from": {"id": 13, "first_name": "Leo"},
            "text": "/start",
        }
    )
    assert out == "start"
    assert enviados
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    enviados = []
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: enviados.append(a[1]),
    )
    monkeypatch.setattr(telegram_sales, "_preco", lambda: "24,90")
    passado = datetime.now(timezone.utc) - timedelta(hours=4)
    telegram_leads.upsert_start(
        "22",
        username="x",
        first_name="Ana",
        next_rmk_at=passado,
    )
    out = telegram_sales.process_due()
    assert out["due"] == 1
    assert out["resultados"][0]["ok"] is True
    lead = telegram_leads.get("22")
    assert lead["rmk_step"] == 1
    assert enviados and "vip" in enviados[0].lower()


def test_rmk_manda_foto_do_bloco(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    fotos = []
    monkeypatch.setattr(
        telegram_sales.funnel,
        "rmk_steps",
        lambda: [
            {
                "id": "r1",
                "minutes": 15,
                "text": "volta aqui",
                "photo_url": "https://x.blob.vercel-storage.com/r.jpg",
                "video_url": "",
                "photo_file_id": "FOTO-RMK",
                "video_file_id": "",
            }
        ],
    )
    monkeypatch.setattr(telegram_sales.funnel, "rmk_gaps_hours", lambda: (0.25, 3.0, 24.0))
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_photo_url",
        lambda *a, **k: fotos.append((a[1], k.get("caption"))) or {},
    )
    monkeypatch.setattr(telegram_sales.telegram, "send_text_message", lambda *a, **k: fotos.append("text"))
    monkeypatch.setattr(telegram_sales, "COVER", __import__("pathlib").Path("nao-existe.jpg"))
    passado = datetime.now(timezone.utc) - timedelta(hours=4)
    telegram_leads.upsert_start("22", username="x", first_name="Ana", next_rmk_at=passado)
    out = telegram_sales.process_due()
    assert out["due"] == 1 and out["resultados"][0]["ok"]
    assert fotos and fotos[0][0] == "FOTO-RMK"
    assert "volta aqui" in (fotos[0][1] or "")
    assert "text" not in fotos


def test_ultimo_rmk_repete_todo_dia(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    monkeypatch.setattr(
        telegram_sales.funnel,
        "rmk_steps",
        lambda: [
            {"id": "r1", "minutes": 15, "text": "um", "loop": True, "loop_minutes": 1440},
            {"id": "r2", "minutes": 180, "text": "dois", "loop": True, "loop_minutes": 1440},
        ],
    )
    monkeypatch.setattr(telegram_sales.telegram, "send_text_message", lambda *a, **k: {})
    monkeypatch.setattr(telegram_sales, "COVER", __import__("pathlib").Path("nao"))
    telegram_leads.upsert_start(
        "55", username=None, first_name="Lia", next_rmk_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    telegram_leads.mark("55", rmk_step=1, next_rmk_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    out = telegram_sales.process_due()
    assert out["due"] == 1
    lead = telegram_leads.get("55")
    assert lead["status"] == "active"
    assert lead["rmk_step"] == 1
    nxt = datetime.fromisoformat(str(lead["next_rmk_at"]))
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=timezone.utc)
    espera = (nxt - datetime.now(timezone.utc)).total_seconds()
    assert espera > 20 * 3600


def test_rmk_para_se_loop_desligado(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    monkeypatch.setattr(
        telegram_sales.funnel,
        "rmk_steps",
        lambda: [{"id": "r1", "minutes": 15, "text": "fim", "loop": False, "loop_minutes": 1440}],
    )
    monkeypatch.setattr(telegram_sales.telegram, "send_text_message", lambda *a, **k: {})
    telegram_leads.upsert_start(
        "56", username=None, first_name="Lia", next_rmk_at=datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    telegram_sales.process_due()
    assert telegram_leads.get("56")["status"] == "stopped"


def test_parar_tira_da_fila(monkeypatch) -> None:
    _sqlite_mem(monkeypatch)
    monkeypatch.setattr(telegram_sales.telegram, "send_text_message", lambda *a, **k: {})
    telegram_leads.upsert_start(
        "33",
        username=None,
        first_name="Joao",
        next_rmk_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    telegram_sales.handle_private_message(
        {
            "chat": {"type": "private", "id": 33},
            "from": {"id": 33, "first_name": "Joao"},
            "text": "/parar",
        }
    )
    assert telegram_leads.get("33")["status"] == "stopped"
    assert telegram_leads.due() == []


def test_sync_profile_usa_cover(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    monkeypatch.setattr(telegram_sales, "_cache_perfil", lambda: {})
    chamados = []
    monkeypatch.setattr(
        telegram_sales.telegram, "set_my_name", lambda *a, **k: chamados.append("name")
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "set_my_short_description",
        lambda *a, **k: chamados.append("short"),
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "set_my_description",
        lambda *a, **k: chamados.append("desc"),
    )
    monkeypatch.setattr(
        telegram_sales.telegram, "set_my_commands", lambda *a, **k: chamados.append("cmd")
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "set_my_profile_photo",
        lambda *a, **k: chamados.append("foto"),
    )
    monkeypatch.setattr("app.store.runtime.set", lambda *a, **k: None)
    out = telegram_sales.sync_profile()
    assert "name" in chamados
    assert "desc" in chamados
    assert out.get("description") == "ok"
    assert out.get("foto") in {"ok", "ausente", "erro", "rate_limit"}


def test_recorte_cartao_640x360() -> None:
    from io import BytesIO

    from PIL import Image

    im = Image.new("RGB", (1200, 800), (40, 0, 20))
    buf = BytesIO()
    im.save(buf, format="JPEG")
    out = telegram_sales.recorte_cartao(buf.getvalue())
    rec = Image.open(BytesIO(out))
    assert rec.size == (640, 360)


def test_urls_video_comeca_pelo_blob(monkeypatch) -> None:
    monkeypatch.setattr(
        telegram_sales,
        "get_settings",
        lambda: type("S", (), {"base_url": "https://dm-ia-hermes.vercel.app"})(),
    )
    urls = telegram_sales._urls_video(
        "start", "https://x.blob.vercel-storage.com/v.mp4"
    )
    assert urls[0] == "https://x.blob.vercel-storage.com/v.mp4"


def test_parse_ref() -> None:
    assert telegram_sales.parse_ref("hermes:tg:99:abc") == "99"
    assert telegram_sales.parse_ref("1265546675660956") is None


def test_identidade_junta_nome_e_arroba() -> None:
    quem = telegram_sales.identidade(
        {
            "id": 99,
            "first_name": "Rogerio",
            "last_name": "Nunes De Alcantara",
            "username": "rogerio",
        }
    )
    assert quem["nome"] == "Rogerio Nunes De Alcantara"
    assert quem["rotulo"] == "Rogerio Nunes De Alcantara @rogerio"
    sem_user = telegram_sales.identidade(
        {"id": 8982868275, "first_name": "J", "last_name": "K"}
    )
    assert sem_user["rotulo"] == "J K 8982868275"


def test_callback_pix(monkeypatch) -> None:
    _sqlite_mem(monkeypatch)
    enviados = []
    monkeypatch.setattr(telegram_sales.telegram, "answer_callback", lambda *a, **k: {})
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: enviados.append(a[1]),
    )
    vistos = []
    monkeypatch.setattr(
        telegram_sales.straton,
        "create_cashin",
        lambda **k: vistos.append(k) or {"pix_code": "00020126PIXFAKE", "qr_code": "", "id": "tx-1"},
    )
    monkeypatch.setattr(telegram_sales, "_preco", lambda: "24,90")
    out = telegram_sales.handle_callback(
        {
            "id": "cb1",
            "data": "pay_pix",
            "from": {
                "id": 44,
                "first_name": "Leo",
                "last_name": "Silva",
                "username": "leosilva",
            },
        }
    )
    assert out == "pix"
    assert enviados and "00020126PIXFAKE" in enviados[0]
    assert vistos[0]["customer_name"] == "Leo Silva @leosilva"
    assert vistos[0]["description"] == "Acesso VIP"


def test_chat_vazio_usa_so_o_banner(monkeypatch) -> None:
    dados = __import__("json").dumps(
        {
            "version": 3,
            "nodes": [
                {
                    "id": "banner",
                    "type": "banner",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "name": "Livia",
                        "short": "priv",
                        "text": "texto do chat vazio",
                        "photo_url": "https://x.blob.vercel-storage.com/b.jpg",
                    },
                },
                {
                    "id": "start",
                    "type": "start",
                    "position": {"x": 0, "y": 1},
                    "data": {"text": "mensagem DEPOIS do start, nao deve ir pro perfil"},
                },
            ],
            "edges": [],
        }
    )
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: dados)
    assert telegram_sales._texto_chat_vazio() == "texto do chat vazio"
    wanted = telegram_sales.perfil_desejado()
    assert wanted["text"] == "texto do chat vazio"
    assert wanted["photo_url"].endswith("b.jpg")
    assert "DEPOIS" not in wanted["text"]


def test_sync_profile_pula_quando_igual(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    wanted = telegram_sales.perfil_desejado()
    monkeypatch.setattr(telegram_sales, "_cache_perfil", lambda: wanted)
    monkeypatch.setattr(
        telegram_sales.telegram,
        "set_my_name",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("não chama")),
    )
    out = telegram_sales.sync_profile()
    assert out["skipped"] is True


def test_sync_profile_sobe_foto_do_banner(monkeypatch) -> None:
    import json

    from app.services import funnel as funnel_mod

    funil = funnel_mod.default_funnel()
    for n in funil["nodes"]:
        if n["type"] == "banner":
            n["data"]["photo_url"] = "https://x.blob.vercel-storage.com/b.jpg"
            n["data"]["text"] = "antes do start"
    monkeypatch.setattr(
        "app.services.funnel.runtime.get",
        lambda *_a, **_k: json.dumps(funil),
    )
    monkeypatch.setattr(telegram_sales, "_cache_perfil", lambda: {})
    monkeypatch.setattr(telegram_sales, "_gravar_cache_perfil", lambda *_a, **_k: None)
    fotos = []
    monkeypatch.setattr(
        telegram_sales.telegram, "set_my_name", lambda *a, **k: None
    )
    monkeypatch.setattr(
        telegram_sales.telegram, "set_my_short_description", lambda *a, **k: None
    )
    monkeypatch.setattr(
        telegram_sales.telegram, "set_my_description", lambda *a, **k: None
    )
    monkeypatch.setattr(
        telegram_sales.telegram, "set_my_commands", lambda *a, **k: None
    )
    monkeypatch.setattr(
        telegram_sales.httpx,
        "get",
        lambda *a, **k: type(
            "R",
            (),
            {
                "content": b"\xff\xd8\xfffake",
                "headers": {"content-type": "image/jpeg"},
                "raise_for_status": lambda self=None: None,
            },
        )(),
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "set_my_profile_photo_bytes",
        lambda data, *a, **k: fotos.append(data) or {},
    )
    out = telegram_sales.sync_profile(force=True)
    assert out["foto"] == "ok"
    assert fotos and fotos[0].startswith(b"\xff\xd8\xff")


def test_start_ignora_foto_do_bloco(monkeypatch) -> None:
    monkeypatch.setattr("app.services.funnel.runtime.get", lambda *_a, **_k: None)
    _sqlite_mem(monkeypatch)
    ordem = []
    monkeypatch.setattr(
        telegram_sales.funnel,
        "start_payload",
        lambda: {
            "id": "start",
            "text": "legenda start",
            "video_url": "",
            "photo_url": "https://x.blob.vercel-storage.com/start.jpg",
            "video_file_id": "",
            "photo_file_id": "FOTO",
        },
    )
    monkeypatch.setattr(telegram_sales, "COVER", __import__("pathlib").Path("nao-existe.jpg"))
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_photo_url",
        lambda *a, **k: ordem.append("photo") or {},
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_photo_bytes",
        lambda *a, **k: ordem.append("capa"),
    )
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: ordem.append("text"),
    )
    monkeypatch.setattr(telegram_sales, "_preco", lambda: "24,90")
    out = telegram_sales.handle_private_message(
        {
            "chat": {"type": "private", "id": 77},
            "from": {"id": 77, "first_name": "Bia"},
            "text": "/start",
        }
    )
    assert out == "start"
    assert ordem == ["text"]


def test_segundo_start_nao_adia_rmk(monkeypatch) -> None:
    _sqlite_mem(monkeypatch)
    primeiro = datetime.now(timezone.utc) + timedelta(minutes=15)
    telegram_leads.upsert_start(
        "88", username="x", first_name="Lia", next_rmk_at=primeiro
    )
    telegram_leads.upsert_start(
        "88",
        username="x",
        first_name="Lia",
        next_rmk_at=datetime.now(timezone.utc) + timedelta(hours=9),
    )
    gravado = str(telegram_leads.get("88")["next_rmk_at"])
    assert primeiro.isoformat()[:19] in gravado


def test_botoes_so_pix() -> None:
    teclado = str(telegram_sales._botoes_venda())
    assert "pay_pix" in teclado
    assert "cartão" not in teclado.lower()
    assert "parar" not in teclado.lower()


def test_dono_nao_entra_no_rmk(monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "999001")
    get_settings.cache_clear()
    _sqlite_mem(monkeypatch)
    enviados = []
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: enviados.append(a),
    )
    out = telegram_sales.handle_private_message(
        {
            "chat": {"type": "private", "id": 999001},
            "from": {"id": 999001, "first_name": "Artur"},
            "text": "/start",
        }
    )
    assert out == "dono"
    assert telegram_leads.get("999001") is None
    assert enviados == []
    get_settings.cache_clear()


def test_rmk_pula_chat_pessoal(monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "999001")
    get_settings.cache_clear()
    _sqlite_mem(monkeypatch)
    telegram_leads.upsert_start(
        "999001",
        username=None,
        first_name="Artur",
        next_rmk_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    enviados = []
    monkeypatch.setattr(
        telegram_sales.telegram,
        "send_text_message",
        lambda *a, **k: enviados.append(a),
    )
    out = telegram_sales.process_due(limit=5)
    assert out["resultados"][0]["via"] == "dono"
    assert telegram_leads.get("999001")["status"] == "stopped"
    assert enviados == []
    get_settings.cache_clear()
