from app.services.payment import claims_payment, needs_support


def test_reconhece_quem_pagou() -> None:
    for frase in [
        "paguei",
        "já paguei",
        "acabei de pagar",
        "fiz o pix",
        "pix feito",
        "fiz o pagamento",
        "pagamento realizado",
        "comprei",
        "já assinei",
        "tá pago",
        "mandei o pix",
        "transferi agora",
        "finalizei a compra",
        "[a pessoa mandou uma foto: um comprovante de Pix de 20 reais]",
    ]:
        assert claims_payment(frase), frase


def test_nao_confunde_quem_ainda_vai_pagar() -> None:
    for frase in [
        "quanto custa?",
        "quero comprar",
        "vou pagar depois",
        "como pago?",
        "posso pagar por pix?",
        "ainda não paguei",
        "não consegui pagar",
        "nao comprei ainda",
        "queria comprar",
        "se eu pagar agora ja recebo?",
        "me manda o link",
        "oi tudo bem?",
        "",
    ]:
        assert not claims_payment(frase), frase


def test_problema_de_acesso_fura_o_silencio() -> None:
    for frase in [
        "não recebi nada",
        "nao chegou o acesso",
        "não consigo entrar",
        "nao consegui entrar no telegram",
        "tô sem acesso",
        "cadê o link?",
        "como acesso?",
        "deu erro aqui",
        "o link expirou",
    ]:
        assert needs_support(frase), frase


def test_papo_solto_nao_vira_suporte() -> None:
    for frase in [
        "vc é linda",
        "oi?",
        "me manda mais foto",
        "tem conteudo novo?",
        "bom dia gata",
        "",
    ]:
        assert not needs_support(frase), frase
