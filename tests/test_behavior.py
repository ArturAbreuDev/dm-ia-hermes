from app.services.sales_agent import _should_use_name
from app.services.timing import reply_plan
from app.services.voice import _HOT_PATTERNS, _strip_for_speech


def test_audio_so_em_palavra_chave_forte() -> None:
    assert _HOT_PATTERNS.search("voce vende conteudo?")
    assert _HOT_PATTERNS.search("tem pack?")
    assert _HOT_PATTERNS.search("quanto custa")
    assert _HOT_PATTERNS.search("quero comprar")


def test_audio_nao_dispara_em_conversa_comum() -> None:
    assert not _HOT_PATTERNS.search("oi tudo bem?")
    assert not _HOT_PATTERNS.search("que foto linda")
    assert not _HOT_PATTERNS.search("me manda o link")
    assert not _HOT_PATTERNS.search("quero te conhecer")


def test_giria_e_expandida_antes_de_falar() -> None:
    assert _strip_for_speech("mt bom nsei se vou") == "muito bom não sei se vou."
    assert _strip_for_speech("sla tbm quero ss") == "sei lá também quero sim."


def test_nome_entra_na_primeira_resposta() -> None:
    assert _should_use_name("Gabriela", [])


def test_nome_nao_repete_em_sequencia() -> None:
    historico = [{"role": "assistant", "text": "Gabriela, oi!"}]
    assert not _should_use_name("Gabriela", historico)


def test_sem_nome_nao_usa_nome() -> None:
    assert not _should_use_name(None, [])


def test_digitando_nunca_passa_do_limite_do_instagram() -> None:
    longa = "a" * 900
    for hora in range(24):
        from datetime import datetime, timedelta, timezone

        agora = datetime(2026, 9, 11, hora, tzinfo=timezone(timedelta(hours=-3)))
        assert reply_plan(longa, now=agora).typing <= 15.0
