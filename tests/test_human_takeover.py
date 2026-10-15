import json
import time

from app.api.webhook import process_instagram_event
from app.config import get_settings
from app.store import memory

CONTATO = "1265546675660956"
CONTA = get_settings().instagram_id or "17841400000000000"


def _evento_do_usuario(texto, mid):
    return {
        "object": "instagram",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": CONTATO},
                        "recipient": {"id": CONTA},
                        "message": {"mid": mid, "text": texto},
                    }
                ]
            }
        ],
    }


def _eco(texto, mid):
    """Mensagem que saiu da conta: o contato está no recipient, não no sender."""
    return {
        "object": "instagram",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": CONTA},
                        "recipient": {"id": CONTATO},
                        "message": {"mid": mid, "text": texto, "is_echo": True},
                    }
                ]
            }
        ],
    }


def _limpar():
    lead = memory.get_lead(CONTATO)
    lead.pop("human_reply_at", None)
    memory.save_lead(CONTATO, lead)


def test_eco_manual_pausa_o_bot() -> None:
    _limpar()
    assert memory.human_pause_seconds(CONTATO) == 0

    process_instagram_event(_eco("oi amor, sou eu mesma", f"manual-{time.time()}"))

    restante = memory.human_pause_seconds(CONTATO)
    janela = get_settings().human_takeover_minutes * 60
    assert restante > janela - 30
    _limpar()


def test_eco_manual_entra_no_historico() -> None:
    """O bot precisa saber o que ela disse à mão, senão repete ou se contradiz."""
    _limpar()
    frase = f"combinado então, te chamo depois {time.time()}"
    process_instagram_event(_eco(frase, f"manual-hist-{time.time()}"))
    assert memory.last_assistant_text(CONTATO) == frase
    _limpar()


def test_eco_do_proprio_bot_nao_pausa() -> None:
    """Nosso envio é gravado com o mid da API, então o eco dele é reconhecido."""
    _limpar()
    mid = f"bot-{time.time()}"
    memory.save_message(CONTATO, "assistant", "tenho simm 👀", mid=mid)

    process_instagram_event(_eco("tenho simm 👀", mid))
    assert memory.human_pause_seconds(CONTATO) == 0
    _limpar()


def test_eco_reconhecido_pelo_texto_quando_o_mid_difere() -> None:
    """Rede de segurança: se o eco chegar antes de gravarmos o mid."""
    _limpar()
    memory.save_message(CONTATO, "assistant", "escolhe aí 😏", mid=f"nosso-{time.time()}")

    process_instagram_event(_eco("escolhe aí 😏", f"outro-mid-{time.time()}"))
    assert memory.human_pause_seconds(CONTATO) == 0
    _limpar()


def test_bot_volta_quando_a_janela_vence(monkeypatch) -> None:
    _limpar()
    memory.mark_human_reply(CONTATO)
    assert memory.human_pause_seconds(CONTATO) > 0

    monkeypatch.setenv("HUMAN_TAKEOVER_MINUTES", "0")
    get_settings.cache_clear()
    assert memory.human_pause_seconds(CONTATO) == 0

    monkeypatch.delenv("HUMAN_TAKEOVER_MINUTES", raising=False)
    get_settings.cache_clear()
    _limpar()


def test_durante_a_pausa_a_ia_nem_e_chamada(monkeypatch) -> None:
    """O que o usuário pediu: ela mandou à mão, o bot não abre a boca."""
    _limpar()
    from app.api import webhook as modulo

    chamadas = []
    monkeypatch.setattr(
        modulo, "generate_sales_reply", lambda *a, **k: chamadas.append(a) or None
    )

    process_instagram_event(_eco("deixa que eu falo", f"manual-{time.time()}"))
    process_instagram_event(_evento_do_usuario("quanto custa?", f"user-{time.time()}"))
    assert chamadas == []

    # Vencida a janela sem mensagem nova dela, o bot volta sozinho.
    monkeypatch.setenv("HUMAN_TAKEOVER_MINUTES", "0")
    get_settings.cache_clear()
    process_instagram_event(_evento_do_usuario("quanto custa?", f"user2-{time.time()}"))
    assert len(chamadas) == 1

    monkeypatch.delenv("HUMAN_TAKEOVER_MINUTES", raising=False)
    get_settings.cache_clear()
    _limpar()


def test_eco_sem_texto_ainda_pausa() -> None:
    """Ela pode ter mandado uma foto ou um áudio na mão."""
    _limpar()
    update = _eco("", f"midia-{time.time()}")
    del update["entry"][0]["messaging"][0]["message"]["text"]
    process_instagram_event(update)
    assert memory.human_pause_seconds(CONTATO) > 0
    _limpar()
