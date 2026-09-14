"""Confere a chegada ousada e o corte depois do link."""

from __future__ import annotations

import sys

from app.config import get_settings
from app.services import canned, engagement

sys.stdout.reconfigure(encoding="utf-8")

erros = 0


def cobrar(condicao: bool, rotulo: str) -> None:
    global erros
    if not condicao:
        erros += 1
    print(f"  {'ok   ' if condicao else 'ERRO '} {rotulo}")


print("--- chegada ousada na PRIMEIRA mensagem pede o áudio de abertura ---")
for frase in [
    "você é muito linda",
    "que gata",
    "gostosa",
    "quero te comer",
    "manda nudes",
    "tô com tesão em você",
    "vamos transar",
]:
    stance = engagement.decide({}, frase, paid=False)
    cobrar(stance.abertura and not stance.silent, f"{frase!r} -> {stance.reason}")

print("\n--- mas 'tudo bem' não é ousadia, e não ganha áudio ---")
for frase in ["oi", "oi tudo bem?", "tudo bom vc", "bom dia", "como funciona?", "quanto custa?"]:
    stance = engagement.decide({}, frase, paid=False)
    cobrar(not stance.abertura, f"{frase!r} -> {stance.reason}")

print("\n--- e só na primeira: depois disso é papo seco, não áudio de novo ---")
stance = engagement.decide({"replies": 1}, "você é linda", paid=False)
cobrar(not stance.abertura and stance.reason == "so_papo", f"segunda vez -> {stance.reason}")

print("\n--- o áudio de abertura fala o nome da pessoa ---")
com_nome = canned.abertura("Rafael")
cobrar("rafael" in com_nome.texto, f"{com_nome.texto[:40]!r}...")
cobrar("telegram" in com_nome.texto.lower(), "diz que o lugar é o telegram")
cobrar("reservado" in com_nome.texto, "diz que é mais reservado")
cobrar("escolher o plano" in com_nome.texto, "diz para escolher o plano")
cobrar("encaminhado" in com_nome.texto, "diz que é encaminhado")
cobrar("?" not in com_nome.texto, "não pergunta nada")
cobrar("amor" in canned.abertura(None).texto, "sem nome, ela chama de amor")
cobrar(canned.abertura("Ana").campo == "audio_abertura", "tem campo próprio no lead")

print("\n--- depois do link: dúvida ela responde, o resto ela responde uma vez e some ---")
com_link = {"link_sent": True, "link_sent_at": 3, "replies": 3}
for frase in ["como funciona?", "não foi pro telegram", "quanto custa?", "vou pagar agora"]:
    stance = engagement.decide(dict(com_link), frase, paid=False)
    cobrar(not stance.silent and stance.farewell is None, f"sobre a compra: {frase!r}")

for frase in ["e vc gosta de que", "tudo bem?", "você é linda", "quero te ver ao vivo"]:
    stance = engagement.decide(dict(com_link), frase, paid=False)
    cobrar(
        not stance.silent and stance.farewell is not None,
        f"fora do assunto, 1a vez: {frase!r} -> {stance.reason}",
    )
    stance = engagement.decide(
        {"link_sent": True, "link_sent_at": 3, "replies": 4}, frase, paid=False
    )
    cobrar(stance.silent, f"fora do assunto, 2a vez: {frase!r} -> {stance.reason}")

print("\n--- erro de pagamento fura tudo, sempre ---")
stance = engagement.decide(
    {"link_sent": True, "link_sent_at": 3, "replies": 9}, "o pix deu erro", paid=False
)
cobrar(not stance.silent, f"pix com erro -> {stance.reason}")

print(f"\n{erros} erro(s)")
sys.exit(1 if erros else 0)
