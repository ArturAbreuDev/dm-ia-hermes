from app.config import get_settings
from app.services import engagement


def test_reconhece_quem_quer_de_graca() -> None:
    for frase in [
        "me manda uma foto",
        "manda um nude",
        "so uma previa vai",
        "tem como de graça?",
        "não tenho dinheiro",
        "tô duro hoje",
        "me da uma amostra",
        "pago depois",
        "faz por menos",
    ]:
        assert "graca" in engagement.read_flags(frase), frase


def test_reconhece_quem_acha_que_e_bot() -> None:
    for frase in [
        "vc é um bot né",
        "você é uma ia?",
        "isso é automatico",
        "é chatgpt isso",
        "resposta automatica",
        "é a livia mesmo?",
    ]:
        assert "ia" in engagement.read_flags(frase), frase


def test_reconhece_erro_de_pagamento() -> None:
    for frase in [
        "o pix deu erro",
        "o link não funciona",
        "pagamento recusado",
        "nao consigo pagar",
        "o qr code expirou",
        "cartão recusado",
    ]:
        assert "erro_pagamento" in engagement.read_flags(frase), frase


def test_reconhece_quem_quer_gravar_ou_encontrar() -> None:
    for frase in [
        "vc grava com fã?",
        "quero gravar com vc",
        "eu pago bem pra gravar com vc",
        "me chama pra gravar vai",
        "vamos marcar então",
        "faz video chamada?",
        "vamos sair juntos",
        "quanto pra te ver pessoalmente?",
        "tem video personalizado?",
        "queria te conhecer pessoalmente",
        "bora marcar algo",
        "vc faz programa?",
    ]:
        assert "ao_vivo" in engagement.read_flags(frase), frase


def test_conversa_normal_nao_levanta_bandeira() -> None:
    for frase in [
        "quanto custa?",
        "quero comprar",
        "que horas vc postou isso?",
        "[a pessoa te marcou no story dela: uma foto do cachorro]",
        "vou gravar um audio pra vc",
        "",
    ]:
        assert not engagement.read_flags(frase), frase


def test_sala_e_elogio_sao_papo() -> None:
    for frase in ["oi tudo bem?", "tudo bom vc", "e aí, beleza?", "vc é linda", "que gata"]:
        assert "papo" in engagement.read_flags(frase), frase


def test_a_compra_vence_o_papo() -> None:
    """Um "oi linda, quanto custa" é cliente, não conversa fiada."""
    for frase in ["oi linda, quanto custa?", "gata, como funciona?", "tudo bem? quero comprar"]:
        assert "papo" not in engagement.read_flags(frase), frase


def test_teto_cai_para_quem_so_faz_sala() -> None:
    teto = get_settings().small_talk_replies
    assert engagement.decide({"replies": teto - 1}, "tudo bem?", False).farewell is not None
    assert engagement.decide({"replies": teto}, "vc é linda", False).silent
    # Mas o teto curto é da mensagem de agora: falar de compra devolve a conversa.
    assert not engagement.decide({"replies": teto}, "quanto custa?", False).silent
    assert not engagement.decide({"replies": teto}, "como funciona?", False).silent


def test_conta_as_vezes_que_foi_so_sala() -> None:
    stance = engagement.decide({"replies": 2, "chat_strikes": 2}, "tudo bem?", False)
    assert "chat_strikes" in stance.counters
    assert stance.repeats == 2


def test_trava_de_vez_quem_trata_como_garota_de_programa() -> None:
    for frase in ["vc é gp?", "quanto vc cobra pela noite", "faz programa?", "qual seu cachê"]:
        stance = engagement.decide({}, frase, False)
        assert stance.silent and stance.mute, frase
    # Vale até para quem já pagou e para quem fala de comprar na mesma frase.
    assert engagement.decide({}, "quanto vc cobra", True).mute
    assert engagement.decide({"replies": 2}, "quero comprar, mas vc é gp?", False).mute


def test_gp_de_formula_1_nao_trava_ninguem() -> None:
    for frase in ["tô assistindo o gp de fórmula 1", "o gp foi emocionante"]:
        assert not engagement.decide({}, frase, False).mute, frase


def test_esfria_e_desiste_de_quem_insiste_em_gravar() -> None:
    limite = get_settings().live_strikes
    quente = engagement.decide({}, "quero gravar com vc", False)
    assert quente.repeats == 0 and not quente.silent
    ultima = engagement.decide({"live_strikes": limite - 1}, "vamos marcar", False)
    assert ultima.farewell is not None
    assert engagement.decide({"live_strikes": limite}, "vamos marcar", False).silent


def test_erro_de_pagamento_nunca_corta() -> None:
    """Quem está tentando pagar é o oposto de quem deve ser cortado."""
    lead = {"replies": 999, "free_strikes": 9, "ai_strikes": 9, "link_sent": True}
    stance = engagement.decide(lead, "o pix deu erro", paid=False)
    assert not stance.silent


def test_cala_depois_de_insistir_de_graca() -> None:
    limite = get_settings().freebie_strikes
    assert engagement.decide({"free_strikes": limite}, "me manda uma foto", False).silent


def test_cala_quem_insiste_que_e_bot() -> None:
    limite = get_settings().ai_strikes
    assert engagement.decide({"ai_strikes": limite}, "vc é um bot", False).silent


def test_cala_conversa_longa_sem_compra() -> None:
    teto = get_settings().max_replies_without_sale
    assert engagement.decide({"replies": teto}, "oi", False).silent
    assert not engagement.decide({"replies": teto - 2}, "oi", False).silent


def test_desiste_mais_rapido_depois_do_link() -> None:
    """Ele já tem o link. Se não pagou, mais conversa não resolve."""
    settings = get_settings()
    lead = {"replies": 4, "link_sent": True, "link_sent_at": 1}
    assert lead["replies"] >= 1 + settings.max_replies_after_link - 3
    gasto = 1 + settings.max_replies_after_link
    assert engagement.decide({**lead, "replies": gasto}, "oi", False).silent
    assert not engagement.decide({**lead, "replies": gasto - 2}, "oi", False).silent


def test_avisa_que_esta_saindo_na_ultima() -> None:
    teto = get_settings().max_replies_without_sale
    stance = engagement.decide({"replies": teto - 1}, "oi", False)
    assert not stance.silent
    assert stance.farewell is not None
    assert stance.farewell.doing


def test_pos_venda_cala_mas_atende_suporte() -> None:
    teto = get_settings().post_payment_replies
    gasto = {"paid": True, "paid_replies": teto}
    assert engagement.decide(gasto, "oi?", paid=True).silent
    suporte = engagement.decide(gasto, "não consegui entrar no telegram", paid=True)
    assert not suporte.silent
    assert suporte.support
