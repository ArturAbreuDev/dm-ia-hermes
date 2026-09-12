import sys
import uuid

from app.services import engagement
from app.services.sales_agent import generate_sales_reply
from app.store import memory

sys.stdout.reconfigure(encoding="utf-8")

# As frases que fizeram ela errar e as variações prováveis.
CASOS = [
    "nao foi pro telegram, foi pra uma pagina de pagamento",
    "abriu outra coisa, nao abriu o telegram",
    "[a pessoa mandou uma foto: a tela de um site mostrando planos de assinatura, "
    "com a opção PREMIUM de R$ 30,00 em pagamento único e uma lista de vantagens]",
    "so tem os planos ali, onde ta o grupo?",
    "esse link ta certo?",
]

for texto in CASOS:
    thread = f"fluxo-{uuid.uuid4().hex[:8]}"
    memory.save_message(thread, "user", "quero comprar")
    memory.save_message(
        thread, "assistant", "é 10, 20 ou 30, escolhe aí: https://botgram.club/livia-gomes-fotos"
    )
    stance = engagement.decide(memory.get_lead(thread), texto, False)
    result = generate_sales_reply(
        thread, texto, first_name="Bruno", stance=stance,
        must_reply=texto.startswith("["),
    )
    print(f"  > {texto[:110]}")
    print(f"    {result.reply or '<<silencio>>'}\n")
