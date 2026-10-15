from app.services import alert, engagement


def _motivo(texto: str, lead: dict | None = None, paid: bool = False) -> str | None:
    lead = lead or {}
    return alert.motivo(texto, engagement.read_flags(texto), paid, lead)


def test_avisa_quem_fala_de_comprar() -> None:
    for frase in [
        "quanto custa?",
        "qual o valor",
        "me manda o link",
        "quero comprar",
        "vou pagar agora",
        "como faço pra pagar",
    ]:
        assert _motivo(frase) == "quer_comprar", frase


def test_avisa_quem_tentou_pagar_e_deu_erro() -> None:
    assert _motivo("o pix deu erro") == "erro_pagamento"
    assert _motivo("não consigo pagar") == "erro_pagamento"


def test_avisa_quem_esta_no_checkout_com_duvida() -> None:
    com_link = {"link_sent": True}
    assert _motivo("como funciona?", com_link) == "duvida_com_link"
    assert _motivo("não foi pro telegram", com_link) == "duvida_com_link"
    # Sem o link na mão, "como funciona" é pergunta de vitrine, não de caixa.
    assert _motivo("como funciona?") != "duvida_com_link"


def test_pagou_vem_antes_de_tudo() -> None:
    assert _motivo("quanto custa?", paid=True) == "pagou"


def test_nao_avisa_conversa_comum() -> None:
    for frase in ["oi", "tudo bem?", "você é linda", "e vc gosta de que", "bom dia", ""]:
        assert _motivo(frase) is None, frase


def test_avisa_quem_nao_tem_telegram() -> None:
    assert _motivo("nao tenho telegram") == "sem_telegram"


def test_nao_repete_o_mesmo_aviso_para_a_mesma_pessoa() -> None:
    """O campo no lead é o que impede cinco pushes do mesmo "quanto custa"."""
    campo = alert._MOTIVOS["quer_comprar"][0]
    assert alert._enviar("123", "quer_comprar", "quanto custa?", {campo: True}) is False


def test_texto_do_aviso_diz_o_essencial() -> None:
    texto = alert._texto(
        "QUER COMPRAR",
        "999",
        "quanto custa?",
        {"replies": 4, "link_sent": True},
        {"name": "Rafael Barradas", "username": "rafael.barradas1812"},
        calada=True,
    )
    assert "QUER COMPRAR" in texto
    assert "Rafael Barradas" in texto and "@rafael.barradas1812" in texto
    assert "quanto custa?" in texto
    assert "4 respostas" in texto and "link já enviado" in texto
    # A linha que mais importa: ninguém vai responder por nós.
    assert "ELA NÃO VAI RESPONDER" in texto
    assert "instagram.com/rafael.barradas1812" in texto


def test_texto_se_vira_sem_perfil() -> None:
    texto = alert._texto("PAGOU", "999", "paguei", {}, None, calada=False)
    assert "IGSID 999" in texto
    assert "ELA NÃO VAI RESPONDER" not in texto


def test_aviso_ignora_grupo_e_usa_pessoal(monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")
    monkeypatch.setenv("ALERT_CHAT_ID", "-100999")
    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "4242")
    get_settings.cache_clear()
    assert get_settings().chat_dono_privado() == "4242"
    get_settings.cache_clear()


def test_nao_manda_nada_sem_canal_configurado(monkeypatch) -> None:
    """Sem token nem destino o aviso vira log, não exceção."""
    from app.config import get_settings

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("ALERT_CHAT_ID", "")
    monkeypatch.setenv("TELEGRAM_DEFAULT_CHAT_ID", "")
    get_settings.cache_clear()
    assert alert.maybe_notify("123", "quanto custa?", frozenset(), False, {}) is None
    get_settings.cache_clear()
