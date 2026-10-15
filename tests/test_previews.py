from datetime import datetime, timedelta, timezone

from app.services import previews, scheduler
from app.store import runtime, schedule


def _mem_runtime(monkeypatch):
    caixa: dict[str, str] = {}
    monkeypatch.setattr(runtime, "get", lambda k: caixa.get(k))
    monkeypatch.setattr(runtime, "set", lambda k, v: caixa.update({k: v}))
    return caixa


def test_canal_previas_liga_sem_getchatmember(monkeypatch) -> None:
    caixa = _mem_runtime(monkeypatch)
    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "111")
    monkeypatch.setenv("TELEGRAM_GROUP_CHAT_ID", "-100vip")
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(previews, "travar_e_avisar", lambda cid: None)
    monkeypatch.setattr(previews, "bot_e_admin", lambda cid: False)
    ok = previews.lembrar(
        {
            "id": -10059836641779,
            "type": "channel",
            "title": "Livia Gomes - Previas",
        }
    )
    assert ok is True
    assert caixa[previews.CHAVE_ID] == "-10059836641779"
    get_settings.cache_clear()


def test_copy_conversao_leva_pro_bot() -> None:
    from app.config import get_settings

    get_settings.cache_clear()
    texto = previews.legenda("x" * 400)
    assert "t.me/liviagommes_bot" in texto
    assert "24,90" in texto
    assert "xxxx" not in texto
    assert "PIX" in texto
    assert "toda semana" in texto.lower()
    assert "Liberar VIP" in previews._markup_vip()["inline_keyboard"][0][0]["text"]
    assert "t.me/liviagommes_bot" in previews.descricao_canal()
    assert "liviagomesvip_bot" not in previews.checkout_url()


def test_ligar_por_texto_username(monkeypatch) -> None:
    caixa = _mem_runtime(monkeypatch)
    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "111")
    monkeypatch.setenv("TELEGRAM_GROUP_CHAT_ID", "-100vip")
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(previews, "travar_e_avisar", lambda cid: None)
    monkeypatch.setattr(
        "app.services.telegram.get_chat",
        lambda cid: {
            "id": -100999,
            "type": "channel",
            "title": "Livia Gomes - Previas",
        }
        if str(cid).startswith("@")
        else None,
    )
    out = previews.ligar_por_texto("https://t.me/liviaprevias")
    assert out["id"] == "-100999"
    assert caixa[previews.CHAVE_ID] == "-100999"
    get_settings.cache_clear()


def test_ids_candidatos_web_k() -> None:
    cands = previews.ids_candidatos("-10059836641779")
    assert "-10059836641779" in cands
    assert "-59836641779" in cands


def test_channel_post_liga_e_dumpa(monkeypatch) -> None:
    from tests.test_telegram_group import _configurar, _mandar

    _configurar(monkeypatch)
    caixa = _mem_runtime(monkeypatch)
    chamou = {"n": 0}
    monkeypatch.setattr(previews, "travar_e_avisar", lambda cid: None)
    monkeypatch.setattr(
        previews, "publicar_do_funil", lambda **_k: chamou.__setitem__("n", 1) or {"enviados": []}
    )
    r = _mandar(
        {
            "channel_post": {
                "chat": {
                    "id": -10059836641779,
                    "type": "channel",
                    "title": "Livia Gomes - Previas",
                },
                "text": ".",
            }
        }
    )
    assert r.status_code == 200
    assert caixa[previews.CHAVE_ID] == "-10059836641779"
    assert chamou["n"] == 1


def test_titulo_reconhece_porevias() -> None:
    assert previews.titulo_de_previas("livia porevias")
    assert previews.titulo_de_previas("Lívia Prévias")
    assert not previews.titulo_de_previas("VIP compradores")


def test_recusa_chat_pessoal_e_vip(monkeypatch) -> None:
    _mem_runtime(monkeypatch)
    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "111")
    monkeypatch.setenv("TELEGRAM_GROUP_CHAT_ID", "-100222")
    monkeypatch.setenv("TELEGRAM_PREVIEWS_CHAT_ID", "111")
    from app.config import get_settings

    get_settings.cache_clear()
    assert previews.chat_id() == ""
    monkeypatch.setenv("TELEGRAM_PREVIEWS_CHAT_ID", "-100222")
    get_settings.cache_clear()
    assert previews.chat_id() == ""
    monkeypatch.setenv("TELEGRAM_PREVIEWS_CHAT_ID", "-100333")
    get_settings.cache_clear()
    assert previews.chat_id() == "-100333"
    get_settings.cache_clear()


def test_lembrar_liga_pelo_titulo(monkeypatch) -> None:
    caixa = _mem_runtime(monkeypatch)
    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "111")
    monkeypatch.setenv("ALERT_CHAT_ID", "111")
    monkeypatch.setenv("TELEGRAM_GROUP_CHAT_ID", "-100vip")
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(previews, "travar_e_avisar", lambda cid: None)
    monkeypatch.setattr(previews, "bot_e_admin", lambda cid: True)
    ok = previews.lembrar(
        {"id": -100555, "type": "supergroup", "title": "livia porevias"},
        status_bot="administrator",
    )
    assert ok is True
    assert caixa[previews.CHAVE_ID] == "-100555"
    # Pessoal não liga mesmo com título.
    caixa.clear()
    assert not previews.lembrar(
        {"id": 111, "type": "supergroup", "title": "livia porevias"}
    )
    get_settings.cache_clear()


def test_webhook_nao_registra_comprador_na_previa(monkeypatch) -> None:
    from tests.test_telegram_group import _configurar, _mandar

    _configurar(monkeypatch)
    caixa = _mem_runtime(monkeypatch)
    caixa[previews.CHAVE_ID] = "-100555"
    monkeypatch.setattr(previews, "travar_e_avisar", lambda cid: None)
    monkeypatch.setattr(previews, "bot_e_admin", lambda cid: True)
    update = {
        "chat_member": {
            "chat": {
                "id": -100555,
                "type": "supergroup",
                "title": "livia porevias",
            },
            "from": {"id": 1, "first_name": "X"},
            "new_chat_member": {
                "user": {"id": 88, "username": "naoevip", "first_name": "Zé"},
                "status": "member",
            },
        }
    }
    from app.store import telegram_members

    r = _mandar(update)
    assert r.status_code == 200
    assert r.json()["registrados"] == 0
    assert telegram_members.find_by_username("naoevip") is None
    # Ainda liga se ainda não tinha id.
    caixa.clear()
    _mandar(
        {
            "message": {
                "chat": {
                    "id": -100555,
                    "type": "supergroup",
                    "title": "livia porevias",
                },
                "text": "oi",
            }
        }
    )
    assert caixa.get(previews.CHAVE_ID) == "-100555"


def test_agenda_previas_manda_pro_telegram(monkeypatch) -> None:
    _mem_runtime(monkeypatch)
    monkeypatch.setenv("TELEGRAM_PREVIEWS_CHAT_ID", "-100555")
    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "111")
    monkeypatch.setenv("TELEGRAM_GROUP_CHAT_ID", "-100vip")
    from app.config import get_settings

    get_settings.cache_clear()
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
    enviado = {}

    def fake_photo(chat_id, url, caption=None, **kw):
        enviado.update(
            {
                "chat_id": str(chat_id),
                "url": url,
                "caption": caption or "",
                "protect": kw.get("protect_content"),
                "markup": kw.get("reply_markup"),
            }
        )
        return {"message_id": 77}

    monkeypatch.setattr("app.services.telegram.send_photo_url", fake_photo)
    monkeypatch.setattr(
        "app.services.publish.publish",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("não pode ir pro IG")),
    )
    item = schedule.create(
        kind="previas",
        media_url="https://example.com/p.jpg",
        caption="corta",
        scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    out = scheduler.process_due()
    assert out["resultados"][0]["ok"] is True
    assert enviado["chat_id"] == "-100555"
    assert enviado["protect"] is True
    assert "corta" in enviado["caption"]
    assert "toda semana" in enviado["caption"].lower()
    assert "24,90" in enviado["caption"]
    assert "t.me/liviagommes_bot" in enviado["caption"]
    assert "Liberar VIP" in enviado["markup"]["inline_keyboard"][0][0]["text"]
    assert enviado["markup"]["inline_keyboard"][0][0]["url"]
    assert schedule.get(item["id"])["status"] == "published"
    get_settings.cache_clear()


def test_publicar_do_funil_manda_rmk(monkeypatch) -> None:
    _mem_runtime(monkeypatch)
    monkeypatch.setenv("TELEGRAM_PREVIEWS_CHAT_ID", "-100555")
    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "111")
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(previews, "travar_e_avisar", lambda cid: None)
    monkeypatch.setattr(previews, "_garantir_boas_vindas", lambda cid: None)
    monkeypatch.setattr(
        "app.services.funnel.midias_previa",
        lambda: [
            {
                "id": "r1",
                "text": "gostinho",
                "photo_url": "https://cdn.example/a.jpg",
                "video_url": "",
            }
        ],
    )
    enviados = []
    monkeypatch.setattr(
        "app.services.telegram.send_photo_url",
        lambda *a, **k: enviados.append((a, k)) or {"message_id": 9},
    )
    monkeypatch.setattr(previews.time, "sleep", lambda *_a, **_k: None)
    out = previews.publicar_do_funil()
    assert out["enviados"][0]["ok"] is True
    assert enviados
    cap = enviados[0][0][2] if len(enviados[0][0]) > 2 else enviados[0][1].get("caption")
    # caption is positional 3rd or kw
    assert enviados[0][1].get("protect_content") is True
    get_settings.cache_clear()


def test_dono_pede_encaminhar_o_canal(monkeypatch) -> None:
    from tests.test_telegram_group import _configurar, _mandar

    _configurar(monkeypatch)
    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "111")
    from app.config import get_settings

    get_settings.cache_clear()
    _mem_runtime(monkeypatch)
    enviados: list[str] = []
    monkeypatch.setattr(
        "app.services.telegram.send_text_message",
        lambda chat_id, text, **kw: enviados.append(text) or {"message_id": 1},
    )
    r = _mandar(
        {
            "message": {
                "chat": {"id": 111, "type": "private"},
                "from": {"id": 111, "first_name": "Artur"},
                "text": "oi",
            }
        }
    )
    assert r.status_code == 200
    assert r.json()["privado"] == "previas-dica"
    assert any("Encaminha" in t for t in enviados)
    get_settings.cache_clear()


def test_encaminhamento_do_dono_liga_mesmo_sem_titulo(monkeypatch) -> None:
    from tests.test_telegram_group import _configurar, _mandar

    _configurar(monkeypatch)
    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "111")
    from app.config import get_settings

    get_settings.cache_clear()
    caixa = _mem_runtime(monkeypatch)
    monkeypatch.setattr(previews, "travar_e_avisar", lambda cid: None)
    monkeypatch.setattr(previews, "publicar_do_funil", lambda **_k: {"enviados": []})
    monkeypatch.setattr(
        "app.services.telegram.send_text_message",
        lambda *a, **k: {"message_id": 1},
    )
    r = _mandar(
        {
            "message": {
                "chat": {"id": 111, "type": "private"},
                "from": {"id": 111, "first_name": "Artur"},
                "forward_from_chat": {
                    "id": -100888,
                    "type": "channel",
                    "title": "Livia Gomes",
                },
                "text": "oi",
            }
        }
    )
    assert r.status_code == 200
    assert caixa[previews.CHAVE_ID] == "-100888"
    get_settings.cache_clear()


def test_encaminhamento_privado_liga_e_manda_oi(monkeypatch) -> None:
    from tests.test_telegram_group import _configurar, _mandar

    _configurar(monkeypatch)
    caixa = _mem_runtime(monkeypatch)
    enviados: list[tuple] = []
    monkeypatch.setattr(previews, "travar_e_avisar", lambda cid: None)
    monkeypatch.setattr(previews, "bot_e_admin", lambda cid: True)
    monkeypatch.setattr(previews, "publicar_do_funil", lambda **_k: {"enviados": []})
    monkeypatch.setattr(
        "app.services.telegram.send_text_message",
        lambda chat_id, text, **kw: enviados.append((str(chat_id), text, kw))
        or {"message_id": 1},
    )
    r = _mandar(
        {
            "message": {
                "chat": {"id": 111, "type": "private"},
                "from": {"id": 111, "first_name": "Artur"},
                "forward_from_chat": {
                    "id": -100777,
                    "type": "supergroup",
                    "title": "livia porevias",
                },
                "text": "qualquer",
            }
        }
    )
    assert r.status_code == 200
    assert r.json()["privado"] == "previas"
    assert caixa[previews.CHAVE_ID] == "-100777"
    destinos = [e[0] for e in enviados]
    assert "-100777" in destinos
    assert "111" in destinos
    from app.config import get_settings

    get_settings.cache_clear()
