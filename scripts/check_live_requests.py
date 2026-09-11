import sys
import uuid

from app.services import engagement
from app.services.sales_agent import generate_sales_reply
from app.store import memory

sys.stdout.reconfigure(encoding="utf-8")

INSISTENCIA = [
    "vc grava com fã?",
    "sério? eu pago bem pra gravar com vc",
    "vamos marcar então, eu vou até onde vc tiver",
    "qualquer dia desses me chama pra gravar vai",
]

thread = f"gravar-{uuid.uuid4().hex[:8]}"
for texto in INSISTENCIA:
    lead = memory.get_lead(thread)
    stance = engagement.decide(lead, texto, False)
    if stance.silent:
        print(f"  > {texto}")
        print(f"    CALADA ({stance.reason})\n")
        continue

    result = generate_sales_reply(thread, texto, first_name="Bruno", stance=stance)
    memory.save_message(thread, "user", texto)
    if result.reply:
        memory.save_message(thread, "assistant", result.reply)
    for campo in stance.counters:
        memory.bump_lead_counter(thread, campo)

    marca = f" [{stance.reason} x{stance.repeats}]"
    if stance.farewell:
        marca += f" [sai pra {stance.farewell.doing}]"
    print(f"  > {texto}")
    print(f"    {result.reply or '<<silencio>>'}{marca}\n")

print("lead:", memory.get_lead(thread))

print("\nsinais soltos:")
for frase in [
    "vc grava com fã?",
    "quero gravar com vc",
    "faz video chamada?",
    "vamos sair juntos",
    "quanto pra te ver pessoalmente?",
    "tem video personalizado?",
    "quanto custa o pack?",
    "oi tudo bem",
]:
    print(f"  {sorted(engagement.read_flags(frase)) or '-'}  <- {frase}")
