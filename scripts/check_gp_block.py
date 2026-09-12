"""Confere a trava do GP: o que precisa travar e o que não pode travar."""

from __future__ import annotations

import sys

from app.services import engagement

sys.stdout.reconfigure(encoding="utf-8")

DEVE_TRAVAR = [
    "você é gp?",
    "vc e gp",
    "é garota de programa?",
    "você faz programa?",
    "faz programa amor",
    "aceita programa?",
    "quanto você cobra?",
    "cobra quanto pela noite",
    "quanto pra transar",
    "quanto pra passar a noite",
    "quanto custa pra sair comigo",
    "qual seu cachê",
    "você é acompanhante?",
    "pago pra transar com vc",
    "quanto pela hora",
    "faz um programa comigo",
    "gp?",
    "vc é gp mesmo?",
]

NAO_PODE_TRAVAR = [
    "oi tudo bem",
    "quanto custa o conteúdo",
    "quanto é o pack",
    "quanto custa",
    "qual o valor",
    "me manda o link",
    "quero comprar",
    "você é linda",
    "que programa de tv você gosta",
    "tô assistindo o gp de fórmula 1",
    "o gp foi emocionante ontem",
    "vi que você foi no gp",
    "vou pagar agora",
    "quanto custa pra ver tudo",
    "tem mais coisa?",
    "queria gravar com você",
]

erros = 0
print("--- deve travar ---")
for frase in DEVE_TRAVAR:
    stance = engagement.decide({}, frase, paid=False)
    travou = stance.silent and stance.mute
    if not travou:
        erros += 1
    print(f"  {'ok   ' if travou else 'ERRO '} {frase!r}  -> {stance.reason}")

print("\n--- NÃO pode travar ---")
for frase in NAO_PODE_TRAVAR:
    stance = engagement.decide({}, frase, paid=False)
    livre = not stance.mute
    if not livre:
        erros += 1
    print(f"  {'ok   ' if livre else 'ERRO '} {frase!r}  -> {stance.reason}")

print("\n--- trava vence quem já pagou e quem diz querer comprar ---")
for lead, frase, paid in [
    ({}, "quanto você cobra pela noite", True),
    ({"muted": True}, "quanto você cobra", False),
    ({"replies": 2}, "quero comprar, mas antes: você é gp?", False),
]:
    stance = engagement.decide(lead, frase, paid=paid)
    travou = stance.silent and stance.mute
    if not travou:
        erros += 1
    print(f"  {'ok   ' if travou else 'ERRO '} lead={lead} paid={paid} -> {stance.reason}")

print(f"\n{erros} erro(s)")
sys.exit(1 if erros else 0)
