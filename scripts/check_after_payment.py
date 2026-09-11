import sys
import uuid

from app.config import get_settings
from app.services.payment import claims_payment
from app.services.sales_agent import generate_sales_reply
from app.store import memory

sys.stdout.reconfigure(encoding="utf-8")

CHECKOUT = get_settings().checkout_url
thread = f"pagou-{uuid.uuid4().hex[:8]}"

CONVERSA = [
    "oi, vc vende conteudo?",
    "quero sim",
    "paguei",
    "e ai, tem mais coisa?",
    "quanto custa mais um?",
    "nao recebi nada ainda",
    "vc é linda",
]

for texto in CONVERSA:
    if claims_payment(texto):
        memory.mark_paid(thread)
    pago = memory.is_paid(thread)

    result = generate_sales_reply(
        thread, texto, first_name="Gabriela", already_paid=pago
    )
    memory.save_message(thread, "user", texto)
    if result.reply:
        memory.save_message(thread, "assistant", result.reply)

    estado = "PAGO " if pago else "venda"
    resposta = result.reply or f"<<silencio intent={result.intent}>>"
    tem_link = "  <<!! LINK VAZOU !!>>" if CHECKOUT and CHECKOUT in resposta else ""
    print(f"[{estado}] {texto}")
    print(f"     -> {resposta}{tem_link}\n")

print("lead final:", memory.get_lead(thread))
