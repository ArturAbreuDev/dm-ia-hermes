"""Desenha o resumo do dia como imagem, para mandar por WhatsApp/Telegram.

Números vêm do fechamento de 11/09 (endpoint /v1/report em produção).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

L = 1500  # largura
MARGEM = 48
COL = (L - MARGEM * 2 - 40) // 2

FUNDO = "#0c0c0d"
CARTAO = "#15161a"
TRACO = "#26282f"
BRANCO = "#f2f3f5"
CINZA = "#9ba1ab"
FRACO = "#6a707a"
VERDE = "#4ade80"
AMBAR = "#f5b544"
VERMELHO = "#f4685f"
AZUL = "#6aa5f5"

FONTES = Path("C:/Windows/Fonts")


def fonte(nome: str, tam: int) -> ImageFont.FreeTypeFont:
    for arquivo in (nome, "segoeui.ttf", "arial.ttf"):
        caminho = FONTES / arquivo
        if caminho.exists():
            return ImageFont.truetype(str(caminho), tam)
    return ImageFont.load_default()


F_GIGANTE = fonte("segoeuib.ttf", 62)
F_H1 = fonte("segoeuib.ttf", 42)
F_H2 = fonte("segoeuisb.ttf", 25)
F_NUM = fonte("segoeuib.ttf", 40)
F_CORPO = fonte("segoeui.ttf", 21)
F_CORPO_B = fonte("segoeuisb.ttf", 21)
F_ROTULO = fonte("segoeui.ttf", 17)
F_MINI = fonte("segoeui.ttf", 15)

tela = Image.new("RGB", (L, 1500), FUNDO)
d = ImageDraw.Draw(tela)


def largura(texto: str, f) -> float:
    return d.textlength(texto, font=f)


def quebrar(texto: str, f, limite: int) -> list[str]:
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if largura(teste, f) <= limite:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def paragrafo(x: int, y: int, texto: str, f, cor: str, limite: int, espaco: int = 30) -> int:
    for linha in quebrar(texto, f, limite):
        d.text((x, y), linha, font=f, fill=cor)
        y += espaco
    return y


def cartao(x: int, y: int, w: int, h: int) -> None:
    d.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=CARTAO, outline=TRACO, width=1)


# ---------------------------------------------------------------- cabeçalho
y = MARGEM + 8
d.text((MARGEM, y), "PRIV DA LÍVIA  ·  INSTAGRAM DM", font=F_ROTULO, fill=FRACO)
d.text((MARGEM, y + 28), "Resumo de 11 de setembro", font=F_H1, fill=BRANCO)

selo_w, selo_h = 276, 86
selo_x = L - MARGEM - selo_w
d.rounded_rectangle(
    (selo_x, y, selo_x + selo_w, y + selo_h), radius=12, fill="#132a1c", outline=VERDE
)
d.text((selo_x + 26, y + 14), "VALIDOU", font=fonte("segoeuib.ttf", 34), fill=VERDE)
d.text((selo_x + 26, y + 56), "primeira venda no primeiro dia", font=F_MINI, fill=VERDE)

y += 118
d.line((MARGEM, y, L - MARGEM, y), fill=TRACO, width=1)

# ------------------------------------------------------------------ números
y += 34
numeros = [
    ("R$ 10", "faturamento", VERDE),
    ("1", "venda", VERDE),
    ("27", "conversas com lead", BRANCO),
    ("18", "receberam o link", BRANCO),
    ("1.127", "mensagens trocadas", BRANCO),
]
passo = (L - MARGEM * 2) // len(numeros)
for i, (valor, rotulo, cor) in enumerate(numeros):
    x = MARGEM + i * passo
    d.text((x, y), valor, font=F_GIGANTE, fill=cor)
    d.text((x, y + 72), rotulo, font=F_ROTULO, fill=CINZA)

y += 122
d.line((MARGEM, y, L - MARGEM, y), fill=TRACO, width=1)

# -------------------------------------------------------------------- funil
y += 32
d.text((MARGEM, y), "Do primeiro oi até o pagamento", font=F_H2, fill=BRANCO)
y += 44

etapas = [
    ("Pessoas que falaram com ela", 34, CINZA),
    ("Viraram conversa de verdade", 27, AZUL),
    ("Receberam o link do checkout", 18, AZUL),
    ("Pagaram", 1, VERDE),
]
barra_x = MARGEM + 380
barra_max = L - MARGEM - barra_x - 90
for rotulo, valor, cor in etapas:
    d.text((MARGEM, y + 2), rotulo, font=F_CORPO, fill=CINZA)
    w = max(6, int(barra_max * valor / 34))
    d.rounded_rectangle((barra_x, y, barra_x + w, y + 26), radius=6, fill=cor)
    d.text((barra_x + w + 14, y + 3), str(valor), font=F_CORPO_B, fill=BRANCO)
    y += 40

y += 14

# ------------------------------------------------------- dois achados-chave
alto = 268
cartao(MARGEM, y, COL, alto)
d.text((MARGEM + 26, y + 24), "A venda veio da conversa mais curta", font=F_H2, fill=VERDE)
yy = y + 66
yy = paragrafo(
    MARGEM + 26,
    yy,
    "O vitor07742 comprou depois de 9 mensagens dele e 10 dela. "
    "O link do checkout saiu já na 6ª resposta.",
    F_CORPO,
    BRANCO,
    COL - 52,
)
yy += 12
yy = paragrafo(
    MARGEM + 26,
    yy,
    "As três conversas mais longas do dia — 46, 36 e 33 mensagens recebidas — "
    "não venderam nada. Nos outros leads o link só saiu perto da 11ª resposta, "
    "quase o dobro.",
    F_CORPO,
    CINZA,
    COL - 52,
)

x2 = MARGEM + COL + 40
cartao(x2, y, COL, alto)
d.text((x2 + 26, y + 24), "9 de 27 nunca receberam o link", font=F_H2, fill=AMBAR)
yy = y + 66
yy = paragrafo(
    x2 + 26,
    yy,
    "Sete dessas conversas foram longas, entre 5 e 17 respostas dela, e a oferta "
    "simplesmente nunca saiu.",
    F_CORPO,
    BRANCO,
    COL - 52,
)
yy += 12
yy = paragrafo(
    x2 + 26,
    yy,
    "São 89 respostas gastas sem nenhuma proposta de compra. ferreiraantoniomoreira, "
    "alanvitor_tognon e euricelio_faco passaram de 16 respostas cada um sem ver o link "
    "uma única vez.",
    F_CORPO,
    CINZA,
    COL - 52,
)

y += alto + 28

# ------------------------------------------------------- custo e comportamento
alto2 = 246
cartao(MARGEM, y, COL, alto2)
d.text((MARGEM + 26, y + 24), "Quanto custou", font=F_H2, fill=BRANCO)
d.text((MARGEM + 26, y + 70), "US$ 0,47", font=F_NUM, fill=BRANCO)
d.text((MARGEM + 26, y + 118), "790 chamadas · 2,1 mi de tokens na OpenAI", font=F_ROTULO, fill=CINZA)
d.line((MARGEM + 26, y + 152, MARGEM + COL - 26, y + 152), fill=TRACO, width=1)
paragrafo(
    MARGEM + 26,
    y + 170,
    "Cerca de R$ 2,60 contra R$ 10 de receita: sobrou R$ 7,40. Fora disso ainda "
    "entram a voz da ElevenLabs e a taxa da plataforma.",
    F_ROTULO,
    FRACO,
    COL - 52,
    24,
)

cartao(x2, y, COL, alto2)
d.text((x2 + 26, y + 24), "Com quem ela lidou", font=F_H2, fill=BRANCO)
itens = [
    ("3", "pediram para gravar ou se encontrar", AMBAR),
    ("2", "tentaram levar conteúdo de graça", AMBAR),
    ("1", "disse que pagou sem ter pagado", VERMELHO),
    ("1", "não tem conta no Telegram", AMBAR),
]
yy = y + 70
for valor, texto, cor in itens:
    d.text((x2 + 26, yy), valor, font=F_CORPO_B, fill=cor)
    d.text((x2 + 56, yy), texto, font=F_CORPO, fill=CINZA)
    yy += 38

y += alto2 + 28

# ------------------------------------------------------------------ pendência
alto3 = 118
d.rounded_rectangle(
    (MARGEM, y, L - MARGEM, y + alto3), radius=14, fill="#2a1f14", outline=AMBAR, width=1
)
d.text((MARGEM + 26, y + 22), "O que trava o crescimento agora", font=F_H2, fill=AMBAR)
paragrafo(
    MARGEM + 26,
    y + 60,
    "O sistema não sabe quem pagou: a venda do vitor07742 estava no banco sem marca de pago e "
    "precisou ser apontada na mão. Enquanto a Botgram não avisar a compra, ela segue oferecendo "
    "o link para quem já comprou.",
    F_ROTULO,
    "#e8d5b7",
    L - MARGEM * 2 - 52,
    25,
)

y += alto3 + 26
d.text(
    (MARGEM, y),
    "Fonte: banco de produção (Postgres), fuso de São Paulo, fechado às 02:38 de 12/09. "
    "Exclui IDs de teste e as 56 linhas do echo antigo.",
    font=F_MINI,
    fill=FRACO,
)

y += 34
tela = tela.crop((0, 0, L, y))

destino = Path("relatorios")
destino.mkdir(exist_ok=True)
saida = destino / "resumo-11-set.png"
tela.save(saida, "PNG")
print(f"salvo em {saida.resolve()}  ({tela.width}x{tela.height})")
