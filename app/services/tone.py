"""Ajustes no texto da resposta antes de sair, para ela não soar de bot.

O prompt pede para ela ser seca, mas pedido em prompt escorrega. Estas funções
são a garantia: se o modelo encher de pergunta ou de emoji, o texto é aparado
aqui, depois de gerado.
"""

from __future__ import annotations

import re

# Onde ela pode pedir para quebrar a fala em duas mensagens.
SEPARADOR = "||"

_MAX_PARTES = 3

_BASE = (
    "\U0001f000-\U0001faff"  # carinhas, mãos, objetos
    "\U00002600-\U000027bf"  # símbolos e dingbats
    "\U00002190-\U000021ff"  # setas
    "\U00002b00-\U00002bff"
)
# Grudam no emoji anterior em vez de valerem como emoji novo: seletor de
# variação, tom de pele e o quadradinho do teclado numérico.
_MODIFICADOR = "\U0000fe0f\U0001f3fb-\U0001f3ff\U000020e3"

# Um emoji "inteiro": a base, seus modificadores e as partes unidas por ZWJ,
# como a família 👨‍👩‍👦, que é um desenho só e não três.
_EMOJI = re.compile(
    f"[{_BASE}][{_MODIFICADOR}]*(?:\u200d[{_BASE}][{_MODIFICADOR}]*)*"
)

# Pedaços da frase, mantendo a pontuação de cada um.
_TRECHOS = re.compile(r"[^.!?]+[.!?]*")

_LINK = re.compile(r"https?://\S+")


def split_messages(reply: str) -> list[str]:
    """Separa a resposta nas mensagens que devem sair, uma por vez."""
    partes = [pedaco.strip() for pedaco in reply.split(SEPARADOR)]
    partes = [pedaco for pedaco in partes if pedaco]
    if not partes:
        return []
    return partes[:_MAX_PARTES]


def soften(reply: str, previous_assistant: str | None = None) -> str:
    """Tira o excesso de pergunta e de emoji da resposta.

    A pergunta é o vício mais forte: sozinha ela transforma a conversa em
    entrevista. Duas mensagens seguidas terminando em pergunta é o que mais
    entrega que do outro lado tem um robô puxando assunto.
    """
    texto = reply.strip()
    if not texto:
        return texto

    # Mensagem com link é mensagem de venda, e link tem ponto no meio: recortar
    # frase aqui picaria a URL e derrubaria o checkout. Uma pergunta a mais numa
    # mensagem dessas custa muito menos do que um link quebrado.
    if not _LINK.search(texto):
        if "?" in (previous_assistant or ""):
            texto = _sem_pergunta(texto)
        elif texto.count("?") > 1:
            texto = _uma_pergunta(texto)

    return _um_emoji(texto)


def _partes_da_frase(texto: str) -> list[str]:
    achados = _TRECHOS.findall(texto)
    return achados or [texto]


def _sem_pergunta(texto: str) -> str:
    """Derruba os trechos com pergunta. Se sobrar nada, deixa como estava:
    calar a resposta inteira é pior do que uma pergunta a mais."""
    if "?" not in texto:
        return texto
    sobra = " ".join(
        pedaco.strip() for pedaco in _partes_da_frase(texto) if "?" not in pedaco
    ).strip()
    return sobra or texto


def _uma_pergunta(texto: str) -> str:
    """Deixa passar a primeira pergunta e corta as outras."""
    saida, ja_perguntou = [], False
    for pedaco in _partes_da_frase(texto):
        if "?" in pedaco:
            if ja_perguntou:
                continue
            ja_perguntou = True
        saida.append(pedaco.strip())
    junto = " ".join(item for item in saida if item).strip()
    return junto or texto


def _um_emoji(texto: str) -> str:
    """Mantém no máximo um emoji, o primeiro, e tira o resto."""
    achados = list(_EMOJI.finditer(texto))
    if len(achados) <= 1:
        return texto

    for achado in reversed(achados[1:]):
        texto = texto[: achado.start()] + texto[achado.end() :]
    return re.sub(r"[ \t]{2,}", " ", texto).strip()
