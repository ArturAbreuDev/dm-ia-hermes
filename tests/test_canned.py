from app.config import get_settings
from app.services import canned, engagement

CHECKOUT = get_settings().active_checkout_url()


def test_reconhece_duvida_sobre_o_fluxo() -> None:
    for frase in [
        "nao foi pro telegram",
        "não abriu o telegram",
        "caiu numa pagina de pagamento",
        "onde ta o grupo?",
        "esse link ta certo?",
        "abriu outra coisa",
        "so tem os planos ali",
        "como funciona?",
        "não entendi como",
        "me explica melhor",
    ]:
        assert "duvida_fluxo" in engagement.read_flags(frase), frase


def test_conversa_normal_nao_pede_audio_de_fluxo() -> None:
    for frase in ["oi tudo bem", "quanto custa?", "vc é linda", "paguei", ""]:
        assert "duvida_fluxo" not in engagement.read_flags(frase), frase


def test_duvida_recebe_a_explicacao() -> None:
    escolhido = canned.pick(
        "é ali mesmo amor", frozenset({"duvida_fluxo"}), {"link_sent": True}
    )
    assert escolhido is canned.DUVIDA


def test_confuso_sem_link_recebe_a_explicacao_do_comeco() -> None:
    """O áudio de dúvida fala de uma página que essa pessoa ainda não abriu."""
    escolhido = canned.pick("é simples", frozenset({"duvida_fluxo"}), {})
    assert escolhido is canned.GERAL


def test_como_funciona_recebe_a_explicacao_do_comeco() -> None:
    assert canned.pick("é simples", frozenset({"como_funciona"}), {}) is canned.GERAL


def test_link_enviado_recebe_o_geral() -> None:
    escolhido = canned.pick(f"escolhe aí: {CHECKOUT}", frozenset(), {})
    assert escolhido is canned.GERAL


def test_duvida_tem_prioridade_sobre_o_link() -> None:
    escolhido = canned.pick(
        f"é ali mesmo, olha: {CHECKOUT}",
        frozenset({"duvida_fluxo"}),
        {"link_sent": True},
    )
    assert escolhido is canned.DUVIDA


def test_nao_repete_o_mesmo_audio_para_a_mesma_pessoa() -> None:
    assert canned.pick(f"link: {CHECKOUT}", frozenset(), {"audio_fluxo_geral": True}) is None
    assert (
        canned.pick(
            "é ali mesmo",
            frozenset({"duvida_fluxo"}),
            {"audio_fluxo_duvida": True, "audio_fluxo_geral": True, "link_sent": True},
        )
        is None
    )


def test_segunda_duvida_ganha_a_outra_explicacao() -> None:
    """São dois áudios diferentes: quem já ouviu um pode ouvir o outro, uma vez."""
    escolhido = canned.pick(
        "é ali mesmo",
        frozenset({"duvida_fluxo"}),
        {"audio_fluxo_duvida": True, "link_sent": True},
    )
    assert escolhido is canned.GERAL


def test_sem_link_e_sem_duvida_nao_manda_nada() -> None:
    assert canned.pick("oiii tudo bem?", frozenset(), {}) is None


def test_desligavel_pela_config(monkeypatch) -> None:
    monkeypatch.setenv("CANNED_AUDIO_ENABLED", "false")
    get_settings.cache_clear()
    assert canned.pick(f"link: {CHECKOUT}", frozenset(), {}) is None
    monkeypatch.delenv("CANNED_AUDIO_ENABLED", raising=False)
    get_settings.cache_clear()
