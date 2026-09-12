"""Confere a trava de tom: pergunta a mais, emoji a mais e quebra em duas."""

from __future__ import annotations

import sys

from app.services import tone

sys.stdout.reconfigure(encoding="utf-8")

# (o que ela tinha dito antes, o que o modelo devolveu, o que deve sair)
CASOS = [
    # O caso do print: ela perguntou na mensagem anterior e perguntou de novo.
    (
        "sério? às vezes o nada é o melhor kkk o que gosta de fazer no seu tempo livre?",
        "descansar é essencial 😌 me diz uma coisa... você fala assim com todo mundo? kkk",
        "descansar é essencial 😌 me diz uma coisa... kkk",
    ),
    # Sem pergunta antes, uma pergunta passa inteira.
    ("e olha que aqui eu mostro pouquinho", "tenho sim 😏 quer que eu te explique?", None),
    # Duas perguntas na mesma mensagem: só a primeira fica.
    (
        "kkk",
        "tenho sim, quer que eu explique? ou você prefere o link?",
        "tenho sim, quer que eu explique?",
    ),
    # Emoji sobrando é aparado até sobrar um.
    ("oi", "tenho opções de 10, 20 e 30 😏👀🔥", "tenho opções de 10, 20 e 30 😏"),
    # Só sobraria pergunta: melhor mandar a pergunta do que ficar sem resposta.
    ("e você, o que faz?", "e você?", "e você?"),
    # Mensagem seca não é mexida.
    ("oi", "kkk entendi", "kkk entendi"),
    # Emoji com tom de pele conta como um só e não é cortado no meio.
    ("oi", "isso aí 👍🏽", "isso aí 👍🏽"),
    ("oi", "isso aí 👍🏽 demais 🔥", "isso aí 👍🏽 demais"),
    # Coração com seletor de variação também é um.
    ("oi", "obrigada ❤️", "obrigada ❤️"),
    # Mensagem com link fica intacta, mesmo com pergunta depois de pergunta:
    # recortar frase aqui picaria a URL no ponto do .club e mataria a venda.
    (
        "quer que eu te passe?",
        "é 10, 20 ou 30, escolhe aí https://botgram.club/livia-gomes-fotos quer?",
        None,
    ),
]

erros = 0
for anterior, cru, esperado in CASOS:
    saiu = tone.soften(cru, anterior)
    alvo = cru if esperado is None else esperado
    marca = "ok   " if saiu == alvo else "ERRO "
    if saiu != alvo:
        erros += 1
    print(f"  {marca} {cru!r}\n        -> {saiu!r}")
    if saiu != alvo:
        print(f"        esperado {alvo!r}")

print("\n--- quebra em mensagens ---")
for cru, esperado in [
    ("kkk sei || mentiroso", ["kkk sei", "mentiroso"]),
    ("uma frase só", ["uma frase só"]),
    ("a || b || c || d", ["a", "b", "c"]),
    ("  ||  sobrou uma  ||  ", ["sobrou uma"]),
    ("", []),
]:
    saiu = tone.split_messages(cru)
    marca = "ok   " if saiu == esperado else "ERRO "
    if saiu != esperado:
        erros += 1
    print(f"  {marca} {cru!r} -> {saiu}")

print(f"\n{erros} erro(s)")
sys.exit(1 if erros else 0)
