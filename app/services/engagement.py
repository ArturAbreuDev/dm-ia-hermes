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


# Tratou ela como garota de programa: perguntou se é GP, quanto cobra pela noite,
# se faz programa. Aqui não tem escalonamento nem segunda chance. Isso não é
# cliente do que ela vende, é problema, e a conversa morre na hora.
_TRATOU_COMO_GP = re.compile(
    r"(?:"
    # "gp" solto pega o GP de Fórmula 1, então só vale com pessoa em volta.
    r"(?:voc[êe]|vc|tu)\s+(?:[ée]|eh|e)\s+gp\b|\b(?:[ée]|eh)\s+gp\b|\bgp\s*\?|"
    r"\bfaz\s+gp\b|\bgdp\b|garota\s+de\s+programa|"
    r"\bacompanhante\b|\bmich[êe]\b|\bprograminha\b|\bcach[êe]\b|"
    r"(?:faz|fazer|faria|aceita|cobra|rola|tem|marca)\s+(?:um\s+)?programa\b|"
    r"programa\s+completo|"
    r"(?:voc[êe]|vc)\s+[ée]\s+(?:puta|prostituta|garota\s+de\s+programa)|"
    r"\b(?:[ée]|eh)\s+(?:puta|prostituta)\b|"
    r"quanto\s+(?:pra|para|pela|pelo|custa\s+(?:pra|para))\s+"
    r"(?:transar|trepar|comer|te\s+comer|dormir|passar\s+a\s+noite|hora|noite|"
    r"sair\s+comigo|me\s+atender)|"
    r"quanto\s+(?:voc[êe]|vc)\s+cobra|\bcobra\s+quanto\b|"
    r"pago\s+(?:pra|para)\s+(?:transar|dormir|sair|te\s+ver|te\s+comer)"
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
    r"\bqueria\s+(?:comprar|assinar)\b|"
    r"\b(?:pack|assinatura|telegram|privacy|priv)\b|"
    r"tem\s+(?:mais|conte[úu]do|pack)|"
    r"onde\s+(?:vejo|compra|assina)|"
    r"(?:voc[êe]|vc)\s+vende|"
    r"quero\s+(?:ver|o\s+telegram|entrar)\b|"
    # Quem já está no checkout falando do PIX: isso é venda, não papo.
    r"\bpix\b|"
    r"\bqr\s*code\b|\bc[óo]digo\s+(?:pix|copia)|"
    r"\bger(ei|ando|ou)\s+(?:o\s+)?pix\b|"
    r"\bt[ôo]\s+pagando\b|"
    r"\bn[ãa]o\s+(?:caiu|entrou|liberou)\b|"
    r"\bexpirou\b|\bvenceu\b"
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


# Perguntou como é a compra, do zero. É a pergunta mais perto do pagamento que
# existe nessa conta: quem pergunta isso está decidindo. Diferente de
# `_DUVIDA_FLUXO`, que é de quem já abriu o link e se perdeu na página.
_COMO_FUNCIONA = re.compile(
    r"(?:"
    r"como\s+(?:que\s+)?(?:funciona|faz|fa[çc]o|compro|pago)|"
    r"como\s+(?:eu\s+)?(?:fa[çc]o|consigo)\s+(?:pra|para)\s+(?:comprar|pagar|entrar|ver)|"
    r"(?:o\s+)?que\s+(?:que\s+)?[ée]\s+(?:isso|esse|essa)|"
    r"(?:o\s+)?que\s+(?:voc[êe]|vc)\s+vende|"
    r"(?:o\s+)?que\s+(?:que\s+)?tem\s+(?:no|l[áa]|dentro|de)|"
    r"me\s+explica|explica\s+(?:a[íi]|melhor|como|isso)|"
    r"(?:quero|queria)\s+(?:saber|entender)\s+como"
    r")",
    re.IGNORECASE,
)


# Sem Telegram: paga PIX na DM e o pack sai no chat, não no grupo.
_SEM_TELEGRAM = re.compile(
    r"(?:"
    r"n[ãa]o\s+(?:tenho|uso|baixo|quero)\s+(?:o\s+)?telegram|"
    r"sem\s+telegram|"
    r"n[ãa]o\s+(?:uso|tenho)\s+(?:tg|tele)|"
    r"manda\s+(?:aqui|no\s+(?:insta|instagram|chat|direct|dm))|"
    r"s[óo]\s+(?:no|pelo|pra)\s+(?:insta|instagram|chat|direct|aqui)|"
    r"n[ãa]o\s+(?:quero|vou)\s+(?:pro|pro\s+|para\s+o\s+)?telegram|"
    r"pode\s+(?:ser|mandar)\s+(?:no|pelo)\s+(?:insta|instagram|chat)"
    r")",
    re.IGNORECASE,
)
_SO_PAPO = re.compile(
    r"^(?:(?:oi+|ol[áa]|eae|e\s*a[íi]|opa|fala|hey|hi|bom\s+dia|boa\s+(?:tarde|noite))"
    r"[\s,!.?]*)*"
    r"(?:tudo\s+(?:bem|bom|certo|tranquilo|joia)|td\s+(?:bem|bom)|"
    r"como\s+(?:vai|(?:voc[êe]|vc)\s+(?:est[áa]|t[áa])|est[áa]|t[áa])|"
    r"beleza|blz|de\s+boa|tudo\s+em\s+casa)"
    # "tudo bom vc", "como vai você", "tudo bem por aí": o rabinho no fim é a
    # mesma sala, então ele não pode fazer a mensagem deixar de casar.
    r"[\s,!.?]*(?:(?:e\s+)?(?:voc[êe]|vc|tu|contigo|com\s+voc[êe]|por\s+a[íi]|a[íi])"
    r"[\s,!.?]*)?$",
    re.IGNORECASE,
)

# Chegou falando de sexo. Não é ofensa nem motivo para travar nada: é gente que
# já sabe o que quer, e o único erro possível aqui é fazer sala em vez de vender.
_PUTARIA = re.compile(
    r"(?:"
    r"\bgoz\w+|\bpunheta\b|\bbat(?:er|endo)\s+uma\b|"
    r"\bpau\s+(?:duro|grande|na\s+m[ãa]o)\b|\bpiroca\b|\bbucet\w+|\bxoxota\b|"
    r"\b(?:transar|trepar|foder|fuder|meter|metendo)\b|"
    r"\b(?:te|voc[êe]|vc)\s+comer\b|\bcomer\s+(?:voc[êe]|vc|tu)\b|"
    r"\b(?:chupar|chupa|boquete)\b|"
    r"\bsentar?\s+(?:em|no)\s+(?:mim|meu)\b|"
    r"\btes[ãa]o\b|\bnudes?\b|"
    r"\bsafad\w+|\bputinha\b|"
    r"\bquero\s+(?:te\s+)?(?:comer|pegar|chupar|foder)\b"
    r")",
    re.IGNORECASE,
)

# Elogio. Um elogio não tem problema nenhum; o que não vira venda é a conversa
# que só tem isso, e é por isso que o contador existe.
_ELOGIO = re.compile(
    r"(?:"
    r"\b(?:linda|lindona|lind[íi]ssima|gata|gatinha|gostosa|del[íi]cia|delicia|"
    r"maravilhosa|perfeita|deusa|princesa|musa|rainha|bel[íi]ssima|"
    r"encantadora|charmosa|sensacional|perfei[çc][ãa]o)\b|"
    r"(?:voc[êe]|vc|tu)\s+[ée]\s+(?:muito\s+|mto\s+|mt\s+|super\s+|t[ãa]o\s+)?"
    r"(?:linda|bonita|gata|gostosa|perfeita|maravilhosa|incr[íi]vel|especial|diferente)|"
    r"amei\s+(?:seu|sua|voc[êe]|vc)|"
    r"(?:que|q)\s+(?:corpo|olhos|sorriso|boca)\b|"
    r"(?:t[áa]|est[áa])\s+(?:muito\s+)?(?:linda|gata|gostosa|maravilhosa)|"
    r"\bapaixonad\w|\bte\s+amo\b|\bcasa\s+comigo\b"
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
    if _TRATOU_COMO_GP.search(text):
        achados.add("gp")
    if _DUVIDA_FLUXO.search(text):
        achados.add("duvida_fluxo")
    if _COMO_FUNCIONA.search(text):
        achados.add("como_funciona")
    if _SEM_TELEGRAM.search(text):
        achados.add("sem_telegram")
    if _PUTARIA.search(text):
        achados.add("putaria")
    # "papo" é o guarda-chuva dos dois, porque o tratamento é o mesmo: ficar seca.
    # "elogio" existe à parte porque só ele conta como chegada ousada; um "tudo
    # bem" não é ousadia nenhuma e não merece o áudio de abertura.
    if _SO_PAPO.match(text.strip()):
        achados.add("papo")
    if _ELOGIO.search(text):
        achados.update({"papo", "elogio"})

    # Papo é o que sobra quando a mensagem não diz nada além disso. Se ela também
    # pergunta preço ou como funciona, o que manda é a compra, não a sala: senão
    # um "linda, como funciona?" seria tratado como conversa fiada.
    if achados - {"papo", "elogio"} or wants_to_buy(text):
        achados.difference_update({"papo", "elogio"})
    if wants_to_buy(text):
        achados.add("quer_comprar")
    return frozenset(achados)


@dataclass
class Stance:
    """Como ela deve tratar esta conversa agora.

    Quando `silent` é verdadeiro nem chamamos a IA: a conversa morreu e não há
    texto que valha a pena gerar. `farewell` marca a última mensagem antes disso,
    para ela sair dizendo que vai fazer alguma coisa em vez de simplesmente sumir.
    """

    silent: bool = False
    # Pede para quem chama gravar isso no lead: a conversa não fecha só agora,
    # fecha para sempre. Quem escreve é o webhook, para `decide` seguir sem
    # efeito colateral e continuar fácil de testar.
    mute: bool = False
    # Chegada ousada: pede o áudio de abertura, aquele que fala o nome da pessoa
    # e diz que o resto está no Telegram. Quem manda é o webhook, que tem o nome.
    abertura: bool = False
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

    # Vem antes de tudo, inclusive de quem já pagou e de quem diz querer comprar:
    # "quanto você cobra pela noite" casa com preço, e sem esta trava na frente a
    # conversa seguiria pelo caminho da venda. Não tem aviso nem despedida.
    if "gp" in flags:
        return Stance(silent=True, mute=True, reason="tratou_como_gp", flags=flags)

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

    # Chegou na primeira mensagem já elogiando ou já falando de sexo. Quem abre
    # assim não precisa de papo: vai o áudio de abertura com o nome e o link.
    if not _n(lead, "replies") and flags & {"elogio", "putaria"}:
        return contando("replies", abertura=True, reason="chegada_ousada")

    # Sala, elogio, "oi", putaria depois da abertura, foto aleatória: vácuo.
    if "papo" in flags or (not flags and not wants_to_buy(text)):
        return calado("sem_intencao_de_compra")
    if "putaria" in flags and _n(lead, "replies") and not wants_to_buy(text):
        return calado("sem_intencao_de_compra")

    # Depois do link só responde o que é compra. O resto some, sem despedida.
    if lead.get("link_sent"):
        sobre_a_compra = (
            bool(
                flags
                & {
                    "duvida_fluxo",
                    "como_funciona",
                    "erro_pagamento",
                    "quer_comprar",
                    "sem_telegram",
                }
            )
            or wants_to_buy(text)
        )
        if not sobre_a_compra:
            return calado("fora_do_assunto_depois_do_link")

    if "ia" in flags:
        vezes = _n(lead, "ai_strikes")
        if vezes >= settings.ai_strikes:
            return calado("insiste_que_e_bot")
        return contando("replies", "ai_strikes", reason="acha_que_e_ia", repeats=vezes)

    if "graca" in flags:
        vezes = _n(lead, "free_strikes")
        if vezes >= settings.freebie_strikes:
            return calado("so_quer_de_graca")
        if vezes == settings.freebie_strikes - 1 and settings.freebie_strikes > 1:
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
        if vezes == settings.live_strikes - 1 and settings.live_strikes > 1:
            return contando(
                "replies",
                "live_strikes",
                farewell=away_excuse(),
                reason="ultima_ao_vivo",
                repeats=vezes,
            )
        return contando("replies", "live_strikes", reason="quer_ao_vivo", repeats=vezes)

    if "sem_telegram" in flags:
        return contando("replies", reason="sem_telegram")

    respostas = _n(lead, "replies")
    teto = settings.max_replies_without_sale
    if lead.get("link_sent"):
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
