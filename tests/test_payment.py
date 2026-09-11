from app.services.payment import claims_payment


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
