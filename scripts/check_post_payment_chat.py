import sys
import uuid

from app.config import get_settings
from app.services import payment
from app.services.sales_agent import generate_sales_reply
from app.store import memory

sys.stdout.reconfigure(encoding="utf-8")

LIMITE = get_settings().post_payment_replies
thread = f"tagarela-{uuid.uuid4().hex[:8]}"
memory.mark_paid(thread)

CONVERSA = [
    "paguei agora",
    "e ai, tem conteudo novo?",
    "vc é muito linda sabia",
    "me manda mais foto",
    "oi?",
    "ta ai?",
    "nao consegui entrar no telegram",
    "e agora?",
]

for texto in CONVERSA:
    lead = memory.get_lead(thread)
    suporte = payment.needs_support(texto) and int(lead.get("paid_support", 0)) < LIMITE
    if not suporte and int(lead.get("paid_replies", 0)) >= LIMITE:
        print(f"[cortado] {texto}")
        print("     -> <<nem chama a IA: conversa encerrada>>\n")
        continue

    result = generate_sales_reply(thread, texto, already_paid=True, support=suporte)
    memory.save_message(thread, "user", texto)
    if not result.reply:
        print(f"[{'suporte' if suporte else 'pos    '}] {texto}")
        print("     -> <<silencio da IA>>\n")
        continue

    memory.save_message(thread, "assistant", result.reply)
    memory.bump_lead_counter(thread, "paid_support" if suporte else "paid_replies")
    print(f"[{'suporte' if suporte else 'pos    '}] {texto}")
    print(f"     -> {result.reply}\n")

print("lead final:", memory.get_lead(thread))
