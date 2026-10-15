import json

from app.config import get_settings
from app.main import app
from app.store import memory, telegram_members
from fastapi.testclient import TestClient

SEGREDO = "segredo-telegram-teste"
GRUPO = "-1002233445566"
IGSID = "1265546675660956"
client = TestClient(app)


def _configurar(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SEGREDO)
    monkeypatch.setenv("TELEGRAM_GROUP_CHAT_ID", GRUPO)
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.api.telegram_hook.telegram_sales.process_due", lambda limit=3: {}
    )


def _mandar(update, token=SEGREDO):
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["X-Telegram-Bot-Api-Secret-Token"] = token
    return client.post(
        "/webhooks/telegram", content=json.dumps(update).encode(), headers=headers
    )


def _entrada(user_id, username, status="member"):
    return {
        "chat_member": {
            "chat": {"id": int(GRUPO), "type": "supergroup", "title": "Priv"},
            "from": {"id": 999, "first_name": "Livia"},
            "date": 1757600000,
            "old_chat_member": {"user": {"id": user_id}, "status": "left"},
            "new_chat_member": {
                "user": {"id": user_id, "username": username, "first_name": "Bruno"},
                "status": status,
            },
            "invite_link": {"invite_link": "https://t.me/+abc", "creator": {"id": 1}},
        }
    }


def test_recusa_sem_token_secreto(monkeypatch) -> None:
    _configurar(monkeypatch)
    assert _mandar(_entrada(1, "bruno"), token=None).status_code == 403
    assert _mandar(_entrada(1, "bruno"), token="errado").status_code == 403


def test_registra_quem_entrou_pelo_link(monkeypatch) -> None:
    _configurar(monkeypatch)
    resposta = _mandar(_entrada(70001, "brunotelegram"))
    assert resposta.status_code == 200
    assert resposta.json()["registrados"] == 1

    achado = telegram_members.find_by_username("@BrunoTelegram")
    assert achado is not None
    assert achado["user_id"] == "70001"
    assert achado["status"] == "member"


def test_ignora_update_de_outro_grupo(monkeypatch) -> None:
    _configurar(monkeypatch)
    intruso = _entrada(70002, "estranho")
    intruso["chat_member"]["chat"]["id"] = -1009999999999
    assert _mandar(intruso).json()["registrados"] == 0
    assert telegram_members.find_by_username("estranho") is None


def test_saida_do_grupo_muda_o_status(monkeypatch) -> None:
    _configurar(monkeypatch)
    _mandar(_entrada(70003, "saiu_fora"))
    _mandar(_entrada(70003, "saiu_fora", status="left"))
    achado = telegram_members.find_by_username("saiu_fora")
    assert achado["status"] == "left"
    assert achado["status"] not in telegram_members.DENTRO


def test_mensagem_de_servico_tambem_registra(monkeypatch) -> None:
    _configurar(monkeypatch)
    update = {
        "message": {
            "message_id": 10,
            "chat": {"id": int(GRUPO), "type": "supergroup"},
            "new_chat_members": [
                {"id": 70004, "username": "pelo_servico", "first_name": "Carlos"},
                {"id": 70005, "is_bot": True, "username": "botgramclub_bot"},
            ],
        }
    }
    assert _mandar(update).json()["registrados"] == 1
    assert telegram_members.find_by_username("pelo_servico") is not None
    # Bot não é comprador.
    assert telegram_members.find_by_username("botgramclub_bot") is None


def test_start_privado_pelo_webhook(monkeypatch) -> None:
    _configurar(monkeypatch)
    monkeypatch.setattr(
        "app.api.telegram_hook.telegram_sales.handle_private_message",
        lambda msg: "start",
    )
    update = {
        "message": {
            "message_id": 1,
            "chat": {"id": 55, "type": "private"},
            "from": {"id": 55, "first_name": "Ana"},
            "text": "/start",
        }
    }
    r = _mandar(update)
    assert r.status_code == 200
    assert r.json()["privado"] == "start"


def test_confirma_compra_pelo_arroba_igual(monkeypatch) -> None:
    """@ igual nas duas redes é a ponte entre Instagram e Telegram."""
    _configurar(monkeypatch)
    from app.services import purchase, telegram

    monkeypatch.setattr(telegram, "is_in_group", lambda *a, **k: True)
    memory.clear_paid(IGSID)
    _mandar(_entrada(70006, "mesmo_arroba"))

    assert purchase.confirm_via_telegram(IGSID, "mesmo_arroba")
    assert memory.is_paid(IGSID)


def test_nao_confirma_quem_nao_esta_no_grupo(monkeypatch) -> None:
    _configurar(monkeypatch)
    from app.services import purchase

    memory.clear_paid(IGSID)
    assert not purchase.confirm_via_telegram(IGSID, "nunca_vi_esse")
    assert not memory.is_paid(IGSID)


def test_tabela_desatualizada_nao_marca_pago(monkeypatch) -> None:
    """Se ele saiu do grupo, a fonte da verdade é o getChatMember, não a tabela."""
    _configurar(monkeypatch)
    from app.services import purchase, telegram

    monkeypatch.setattr(telegram, "is_in_group", lambda *a, **k: False)
    memory.clear_paid(IGSID)
    _mandar(_entrada(70007, "ja_saiu_de_la"))
    assert not purchase.confirm_via_telegram(IGSID, "ja_saiu_de_la")
    assert not memory.is_paid(IGSID)


def test_sem_grupo_configurado_nao_faz_nada(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_GROUP_CHAT_ID", raising=False)
    get_settings.cache_clear()
    from app.services import purchase

    memory.clear_paid(IGSID)
    assert not purchase.confirm_via_telegram(IGSID, "qualquer_um")


def test_webhook_start_ainda_dispara_rmk(monkeypatch) -> None:
    ticks = []
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SEGREDO)
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.api.telegram_hook.telegram_sales.handle_private_message",
        lambda *_a, **_k: "start",
    )
    monkeypatch.setattr(
        "app.api.telegram_hook.telegram_sales.process_due",
        lambda limit=3: ticks.append(limit) or {"due": 0},
    )
    r = _mandar(
        {
            "message": {
                "chat": {"type": "private", "id": 11},
                "from": {"id": 11, "first_name": "Lia"},
                "text": "/start",
            }
        }
    )
    assert r.status_code == 200
    assert ticks == [3]
