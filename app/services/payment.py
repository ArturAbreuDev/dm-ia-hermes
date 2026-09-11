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


# Quem pagou e não conseguiu acessar merece resposta mesmo com a conversa encerrada.
_SUPORTE = re.compile(
    r"(?:"
    r"\b(?:n[ãa]o|nao|n)\s+(?:recebi|chegou|veio|consigo|consegui|entrou|abriu|abre|funciona)|"
    r"sem\s+acesso|n[ãa]o\s+tenho\s+acesso|"
    r"cad[êe]\s+(?:o|a|meu|minha)|"
    r"link\s+(?:do|de)\s+telegram|"
    r"como\s+(?:acesso|entro|fa[çc]o\s+pra\s+entrar)|"
    r"\bn[ãa]o\s+achei\b|"
    r"\bdeu\s+erro\b|\btravou\b|\bexpirou\b|"
    r"grupo\s+(?:n[ãa]o|nao)"
    r")",
    re.IGNORECASE,
)


def needs_support(text: str) -> bool:
    """Problema de acesso depois da compra. Isso não é papo, é atendimento."""
    return bool(text) and bool(_SUPORTE.search(text))


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
