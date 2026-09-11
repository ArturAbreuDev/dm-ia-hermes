import sys
import uuid
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.services import engagement, payment
from app.services.sales_agent import generate_sales_reply
from app.store import memory

sys.stdout.reconfigure(encoding="utf-8")

S = get_settings()
BRASILIA = timezone(timedelta(hours=-3))


def rodar(titulo, mensagens, pago=False):
    thread = f"clima-{uuid.uuid4().hex[:8]}"
    if pago:
        memory.mark_paid(thread)
    print(f"\n{'=' * 70}\n{titulo}\n{'=' * 70}")

    for texto in mensagens:
        if payment.claims_payment(texto):
            memory.mark_paid(thread)
        lead = memory.get_lead(thread)
        stance = engagement.decide(lead, texto, memory.is_paid(thread))

        if stance.silent:
            print(f"  > {texto}")
            print(f"    CALADA ({stance.reason})\n")
            continue

        result = generate_sales_reply(
            thread, texto, first_name="Bruno", stance=stance,
            must_reply=False, already_paid=memory.is_paid(thread),
        )
        memory.save_message(thread, "user", texto)
        if result.reply:
            memory.save_message(thread, "assistant", result.reply)
        for campo in stance.counters:
            memory.bump_lead_counter(thread, campo)
        if S.checkout_url and S.checkout_url in (result.reply or ""):
            memory.mark_link_sent(thread)

        marca = f" [{stance.reason}]" if stance.reason != "normal" else ""
        if stance.farewell:
            marca += f" [sai pra {stance.farewell.doing}]"
        print(f"  > {texto}")
        print(f"    {result.reply or '<<silencio da IA>>'}{marca}\n")

    print(f"  lead: {memory.get_lead(thread)}")


agora = datetime.now(BRASILIA)
print(f"agora em Brasília: {agora:%H:%M} -> sai pra {engagement.away_excuse().doing}")

rodar("QUEM SÓ QUER DE GRAÇA", [
    "oi gata",
    "me manda uma foto",
    "so uma previa vai",
    "nao tenho dinheiro agora",
])

rodar("QUEM ACHA QUE É IA", [
    "oi",
    "vc é um bot né",
    "isso é resposta automatica",
    "é a livia mesmo?",
])

rodar("ERRO NO PIX", [
    "quero comprar",
    "o pix deu erro",
    "nao consigo pagar",
])

rodar("PAGOU E QUER CONVERSAR", [
    "fiz o pix",
    "e ai tem novidade?",
    "oi?",
    "vc é linda",
])
