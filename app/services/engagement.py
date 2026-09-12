from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.config import get_settings
from app.services import payment
from app.services.timing import Away, away_excuse

# Quer de graça, quer "só uma", quer fiado. Nunca vira venda.
_DE_GRACA = re.compile(
    r"(?:"
    r"de\s+gra[çc]a|gratu[íi]t\w*|\bgr[áa]tis\b|"
    r"sem\s+(?:pagar|dinheiro|grana)|"
    r"n[ãa]o\s+tenho\s+(?:dinheiro|grana|como\s+pagar)|"
    r"t[ôo]\s+(?:duro|liso|quebrado|sem\s+grana)|"
    r"\bfiado\b|"
    r"me\s+(?:d[áa]|manda)\s+(?:uma|um|umas|uns|a[íi])?\s*(?:foto|v[íi]deo|nude|pr[ée]via|amostra|gostosa)|"
    r"manda\s+(?:uma|um)\s+(?:foto|v[íi]deo|nude|pr[ée]via)|"
    r"\b(?:s[óo]|apenas)\s+uma\s+(?:foto|pr[ée]via|amostra)|"
    r"pr[ée]via\s+gr[áa]tis|"
    r"pago\s+depois|"
    r"faz\s+(?:por|um)\s+menos"
    r")",
    re.IGNORECASE,
)

# Desconfia que do outro lado tem um robô. Discutir isso é perder a venda.
_ACHA_QUE_E_IA = re.compile(
    r"(?:"
    r"\b(?:[ée]|eh)\s+(?:um\s+)?(?:bot|rob[ôo]|ia|chatgpt|gpt)\b|"
    r"\bvoc[êe]\s+[ée]\s+(?:uma\s+)?(?:bot|rob[ôo]|ia|m[áa]quina)\b|"
    r"\bvc\s+[ée]\s+(?:uma\s+)?(?:bot|rob[ôo]|ia|m[áa]quina)\b|"
    r"resposta\s+autom[áa]tica|"
    r"isso\s+[ée]\s+autom[áa]tic\w*|"
    r"\bintelig[êe]ncia\s+artificial\b|"
    r"n[ãa]o\s+[ée]\s+(?:voc[êe]|vc)\s+mesm\w|"
    r"\b(?:[ée]|eh)\s+(?:a\s+)?l[íi]via\s+mesm\w"
    r")",
    re.IGNORECASE,
)

# Tentou pagar e o pagamento falhou. Isso é problema técnico, não objeção.
_ERRO_PAGAMENTO = re.compile(
    r"(?:"
    r"(?:pix|pagamento|pagto|link|qr\s*code|c[óo]digo)\s+"
    r"(?:deu\s+erro|n[ãa]o\s+(?:funciona|funcionou|foi|passou|deu|carrega|abre)|"
    r"falhou|recusad\w|expirou|venceu|t[áa]\s+fora)|"
    r"deu\s+erro\s+(?:no|na|ao)\s+(?:pix|pagar|pagamento|link)|"
    r"n[ãa]o\s+(?:consigo|consegui)\s+pagar|"
    r"cart[ãa]o\s+(?:recusad\w|negad\w|n[ãa]o\s+passou)|"
    r"\bpix\s+(?:inv[áa]lido|errado)\b"
    r")",
    re.IGNORECASE,
)


# Quer gravar com ela, marcar um encontro, chamada de vídeo, algo ao vivo.
# Não é pedido absurdo, mas também não é o que está sendo vendido aqui.
_QUER_AO_VIVO = re.compile(
    r"(?:"
    # "grava com fã", "gravar comigo", "gravaria junto"
    r"grav\w*\s+(?:com|junt\w|contigo|comigo)|"
    # "quero gravar", "dá pra gravar", "me chama pra gravar", "aceita gravar"
    r"(?:quero|queria|posso|pode|pod[ei]a|aceita|rola|tem\s+como|d[áa]\s+pra|"
    r"pra|para)\s+grav\w*|"
    r"grava[çc][ãa]o\s+(?:com|junt\w)|"
    r"v[íi]deo\s+(?:personalizad\w|exclusiv\w|s[óo]\s+(?:pra|para)\s+mim)|"
    r"chamada\s+de\s+v[íi]deo|video\s*(?:chamada|call)|\bvideochamada\b|"
    r"te\s+(?:ver|conhecer|encontrar|pegar)\s+(?:pessoalmente|ao\s+vivo|de\s+verdade|um\s+dia)|"
    r"(?:nos|se)\s+(?:ver|encontrar)\b|"
    r"(?:vamos|podemos|bora|d[áa]\s+pra|quero|queria)\s+(?:marcar|combinar|sair|nos\s+ver)|"
    r"(?:marcar|combinar)\s+(?:algo|alguma\s+coisa|uma\s+coisa|um\s+encontro|um\s+dia|"
    r"ent[ãa]o|contigo|comigo)|"
    r"sair\s+(?:comigo|com\s+voc[êe]|com\s+vc|junt\w)|"
    r"\b(?:faz|fazer|faria|rola)\s+(?:um\s+)?programa\b|"
    r"quanto\s+(?:pra|para|custa\s+pra)\s+(?:gravar|sair|te\s+ver|um\s+encontro|te\s+conhecer)|"
    r"\bencontro\b|\bmotel\b|\bdate\b|\bao\s+vivo\b"
    r")",
    re.IGNORECASE,
)


# Intenção clara de comprar. É a única coisa que fura um silenciamento manual.
_QUER_COMPRAR = re.compile(
    r"(?:"
    r"\bvou\s+(?:pagar|comprar|assinar|pegar)\b|"
    r"\bquero\s+(?:pagar|comprar|assinar|o\s+pack|o\s+conte[úu]do|ver\s+as\s+op[çc][õo]es)\b|"
    r"\bvou\s+querer\b|\bt[ôo]\s+dentro\b|\bfechou\b|\bfechado\b|"
    r"(?:me\s+)?manda\s+o\s+link|"
    r"\bcomo\s+(?:pago|compro|fa[çc]o\s+pra\s+(?:pagar|comprar))\b|"
    r"quanto\s+(?:custa|[ée]|sai|fica)|"
    r"\bqual\s+o\s+(?:valor|pre[çc]o)\b|"
    r"\bpode\s+mandar\s+o\s+link\b|"
    r"\bvou\s+fazer\s+o\s+pix\b|"
    r"\bqueria\s+(?:comprar|assinar)\b"
    r")",
    re.IGNORECASE,
)


def wants_to_buy(text: str) -> bool:
    if not text:
        return False
    if payment.claims_payment(text):
        return True
    return bool(_QUER_COMPRAR.search(text))


# Abriu o link e estranhou o que viu, ou ainda não entendeu como é a compra.
_DUVIDA_FLUXO = re.compile(
    r"(?:"
    r"n[ãa]o\s+(?:foi|fui|abriu|abre|caiu|ca[íi]|vai|entrou)\s+"
    r"(?:para\s+o|pro|pra|nos|nas|no|na|o|a)?\s*telegram|"
    r"(?:p[áa]gina|tela|site)\s+de\s+pagamento|"
    r"(?:onde|aonde)\s+(?:t[áa]|est[áa]|fica|[ée])\s+o\s+(?:grupo|telegram|conte[úu]do)|"
    r"(?:esse|este|o)\s+link\s+(?:t[áa]|est[áa])\s+(?:certo|errado)|"
    r"link\s+errado|"
    r"abriu\s+outra\s+coisa|"
    r"s[óo]\s+(?:tem|aparece|apareceu)\s+(?:os\s+)?planos|"
    r"como\s+(?:que\s+)?(?:funciona|[ée])\s*(?:isso|a\s+compra|pra\s+comprar)?\??$|"
    r"n[ãa]o\s+entendi\s+(?:como|nada|direito|bem)|"
    r"me\s+explica\s+(?:melhor|como|direito)"
    r")",
    re.IGNORECASE,
)


def read_flags(text: str) -> frozenset[str]:
    """Lê o que essa mensagem revela sobre a pessoa, não sobre o assunto."""
    if not text:
        return frozenset()
    achados = set()
    if _DE_GRACA.search(text):
        achados.add("graca")
    if _ACHA_QUE_E_IA.search(text):
        achados.add("ia")
    if _ERRO_PAGAMENTO.search(text):
        achados.add("erro_pagamento")
    if _QUER_AO_VIVO.search(text):
        achados.add("ao_vivo")
    if _DUVIDA_FLUXO.search(text):
        achados.add("duvida_fluxo")
    return frozenset(achados)


@dataclass
class Stance:
    """Como ela deve tratar esta conversa agora.

    Quando `silent` é verdadeiro nem chamamos a IA: a conversa morreu e não há
    texto que valha a pena gerar. `farewell` marca a última mensagem antes disso,
    para ela sair dizendo que vai fazer alguma coisa em vez de simplesmente sumir.
    """

    silent: bool = False
    farewell: Away | None = None
    support: bool = False
    reason: str = "normal"
    flags: frozenset[str] = frozenset()
    counters: tuple[str, ...] = field(default_factory=tuple)
    # Quantas vezes ela já ouviu esse mesmo pedido. Serve para o tom esfriar
    # em vez de ela responder a mesma coisa com o mesmo entusiasmo sempre.
    repeats: int = 0


def decide(lead: dict, text: str, paid: bool) -> Stance:
    settings = get_settings()
    flags = read_flags(text)

    def calado(motivo: str) -> Stance:
        return Stance(silent=True, reason=motivo, flags=flags)

    def contando(*campos: str, **extra) -> Stance:
        return Stance(flags=flags, counters=campos, **extra)

    # Silenciado na mão: só volta a existir se falar de comprar ou de pagar.
    if lead.get("muted"):
        if not wants_to_buy(text) and "erro_pagamento" not in flags:
            return calado("silenciado_manualmente")
        # A porta que sobrou tem que abrir mesmo. Um silêncio decidido depois
        # não pode fechá-la, senão o silenciamento vira mudez total.
        return contando("replies", reason="silenciado_mas_quer_comprar")

    if paid:
        teto = settings.post_payment_replies
        if payment.needs_support(text) and _n(lead, "paid_support") < teto:
            return contando("paid_support", support=True, reason="suporte_pos_venda")
        gastas = _n(lead, "paid_replies")
        if gastas >= teto:
            return calado("ja_comprou_conversa_encerrada")
        if gastas == teto - 1:
            return contando(
                "paid_replies", farewell=away_excuse(), reason="ultima_pos_venda"
            )
        return contando("paid_replies", reason="pos_venda")

    # Erro de pagamento é de quem está tentando comprar: isso nunca corta.
    if "erro_pagamento" in flags:
        return contando("replies", reason="erro_pagamento")

    if "ia" in flags:
        vezes = _n(lead, "ai_strikes")
        if vezes >= settings.ai_strikes:
            return calado("insiste_que_e_bot")
        return contando("replies", "ai_strikes", reason="acha_que_e_ia", repeats=vezes)

    if "graca" in flags:
        vezes = _n(lead, "free_strikes")
        if vezes >= settings.freebie_strikes:
            return calado("so_quer_de_graca")
        if vezes == settings.freebie_strikes - 1:
            return contando(
                "replies",
                "free_strikes",
                farewell=away_excuse(),
                reason="ultima_de_graca",
                repeats=vezes,
            )
        return contando("replies", "free_strikes", reason="quer_de_graca", repeats=vezes)

    if "ao_vivo" in flags:
        vezes = _n(lead, "live_strikes")
        if vezes >= settings.live_strikes:
            return calado("insiste_em_gravar")
        if vezes == settings.live_strikes - 1:
            return contando(
                "replies",
                "live_strikes",
                farewell=away_excuse(),
                reason="ultima_ao_vivo",
                repeats=vezes,
            )
        return contando("replies", "live_strikes", reason="quer_ao_vivo", repeats=vezes)

    respostas = _n(lead, "replies")
    teto = settings.max_replies_without_sale
    if lead.get("link_sent"):
        # Ele já tem o link na mão. Se não pagou até agora, conversa não resolve.
        teto = min(teto, _n(lead, "link_sent_at") + settings.max_replies_after_link)
    if respostas >= teto:
        return calado("conversa_longa_sem_compra")
    if respostas == teto - 1:
        return contando("replies", farewell=away_excuse(), reason="ultima_sem_compra")
    return contando("replies", reason="normal")


def _n(lead: dict, campo: str) -> int:
    try:
        return int(lead.get(campo, 0))
    except (TypeError, ValueError):
        return 0
