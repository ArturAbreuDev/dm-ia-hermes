from __future__ import annotations

import re

# Quem já pagou fala no passado. Quem ainda vai pagar fala no futuro ou pergunta.
_PAGOU = re.compile(
    r"(?:"
    r"\bpaguei\b|\bpagando\b|"
    r"fiz\s+o\s+(?:pix|pagamento|pagto)|"
    r"pix\s+(?:feito|enviado|mandado|realizado)|"
    r"pagamento\s+(?:feito|realizado|efetuado|conclu[íi]do|ok)|"
    r"\bcomprei\b|\bassinei\b|"
    r"(?:t[áa]|est[áa])\s+pago\b|"
    r"mandei\s+o\s+pix|\btransferi\b|"
    r"acabei\s+de\s+(?:pagar|comprar)|"
    r"\bcomprovante\b|"
    r"finalizei\s+(?:a\s+)?compra"
    r")",
    re.IGNORECASE,
)

# Freia os casos em que a palavra aparece mas o pagamento não aconteceu.
_NAO_PAGOU = re.compile(
    r"(?:"
    r"\b(?:n[ãa]o|nao|n)\s+(?:consegui\s+)?(?:paguei|comprei|assinei|pagar|comprar)|"
    r"ainda\s+(?:n[ãa]o|nao)|"
    r"\bvou\s+(?:pagar|comprar|assinar)|"
    r"\bquero\s+(?:pagar|comprar|assinar)|"
    r"\bse\s+eu\s+(?:pagar|comprar)|"
    r"\bcomo\s+(?:pago|compro|assino)|"
    r"\bposso\s+(?:pagar|comprar)|"
    r"\bqueria\s+(?:pagar|comprar)|"
    r"\bpretendo\b|"
    r"\bdepois\s+eu\s+(?:pago|compro)"
    r")",
    re.IGNORECASE,
)


def claims_payment(text: str) -> bool:
    """A pessoa está dizendo que já pagou?

    Também pega o comprovante mandado como foto, porque a descrição da imagem
    entra no mesmo texto antes de chegar aqui.
    """
    if not text:
        return False
    if _NAO_PAGOU.search(text):
        return False
    return bool(_PAGOU.search(text))
