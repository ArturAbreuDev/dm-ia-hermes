"""Confere os dois comportamentos novos, sem chamar a OpenAI.

1. "como funciona" tem que virar áudio de explicação + link.
2. Papo furado e elogio têm que baixar o teto e esfriar o tom.
"""

from __future__ import annotations

import sys

from app.config import get_settings
from app.services import canned, engagement, sales_agent

sys.stdout.reconfigure(encoding="utf-8")

erros = 0


def cobrar(condicao: bool, rotulo: str) -> None:
    global erros
    if not condicao:
        erros += 1
    print(f"  {'ok   ' if condicao else 'ERRO '} {rotulo}")


print("--- 'como funciona' é lido como compra, não como papo ---")
for frase in [
    "como funciona?",
    "como funciona isso",
    "como que funciona amor",
    "como faço pra comprar",
    "me explica melhor",
    "o que você vende",
    "o que tem lá dentro",
    "queria entender como funciona",
]:
    flags = engagement.read_flags(frase)
    cobrar("como_funciona" in flags and "papo" not in flags, f"{frase!r} -> {sorted(flags)}")

print("\n--- o áudio certo para cada momento ---")
cobrar(
    canned.pick("", frozenset({"como_funciona"}), {}) is canned.GERAL,
    "sem link ainda -> áudio de explicação do começo",
)
cobrar(
    canned.pick("", frozenset({"duvida_fluxo"}), {}) is canned.GERAL,
    "confuso mas nunca recebeu link -> explicação do começo, não a da página",
)
cobrar(
    canned.pick("", frozenset({"duvida_fluxo"}), {"link_sent": True}) is canned.DUVIDA,
    "já abriu o link e se perdeu -> áudio da página",
)
cobrar(
    canned.pick("", frozenset({"como_funciona"}), {canned.GERAL.campo: True}) is None,
    "já ouviu a explicação -> não repete",
)

print("\n--- o link entra mesmo se o modelo esquecer ---")
settings = get_settings()
link = settings.checkout_link("123")
sem_link = sales_agent._garantir_link("é simples, você escolhe o plano lá", settings, "123")
cobrar(link in sem_link, f"anexou: {sem_link!r}")
cobrar(sales_agent.tone.SEPARADOR in sem_link, "foi como segunda mensagem")
partes = sales_agent.tone.split_messages(sem_link)
cobrar(len(partes) == 2 and link in partes[-1], f"link inteiro na 2a parte: {partes!r}")
com_link = f"olha aí {link}"
cobrar(
    sales_agent._garantir_link(com_link, settings, "123") == com_link,
    "não duplica quando o modelo já mandou",
)

print("\n--- papo furado e elogio ---")
for frase in ["tudo bem?", "oi tudo bem", "e aí, beleza?", "tudo bom vc", "como vai você"]:
    cobrar("papo" in engagement.read_flags(frase), f"sala: {frase!r}")
for frase in ["você é muito linda", "que gata", "nossa que corpo", "amei seu perfil", "gostosa"]:
    cobrar("papo" in engagement.read_flags(frase), f"elogio: {frase!r}")

print("\n--- mas a compra sempre vence o papo ---")
for frase in ["oi linda, quanto custa?", "gata, como funciona?", "tudo bem? quero comprar"]:
    flags = engagement.read_flags(frase)
    cobrar("papo" not in flags, f"{frase!r} -> {sorted(flags)}")

print("\n--- o teto cai para quem só faz sala ---")
teto = settings.small_talk_replies
stance = engagement.decide({"replies": teto - 1}, "tudo bem?", paid=False)
cobrar(stance.farewell is not None, f"na resposta {teto} ela se despede")
stance = engagement.decide({"replies": teto}, "você é linda", paid=False)
cobrar(stance.silent, f"depois de {teto} respostas de sala, ela para")
stance = engagement.decide({"replies": teto}, "quanto custa?", paid=False)
cobrar(not stance.silent, "mas se ele pergunta o preço, ela responde")
stance = engagement.decide({"replies": teto}, "como funciona?", paid=False)
cobrar(not stance.silent, "e se ele pergunta como funciona, também")
stance = engagement.decide({"replies": 2, "chat_strikes": 2}, "tudo bem?", paid=False)
cobrar("chat_strikes" in stance.counters, "conta as vezes que foi só sala")
cobrar(stance.repeats == 2, f"e passa isso para o tom esfriar: repeats={stance.repeats}")

print(f"\n{erros} erro(s)")
sys.exit(1 if erros else 0)
