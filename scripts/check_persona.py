import sys
import uuid

from app.services.sales_agent import _should_use_name, generate_sales_reply

sys.stdout.reconfigure(encoding="utf-8")

print("=== quando o nome entra ===")
historico = []
for i in range(1, 9):
    usa = _should_use_name("Gabriela", historico)
    print(f"  resposta {i}: nome={'SIM' if usa else 'nao'}")
    historico.append({"role": "user", "text": "oi"})
    historico.append(
        {"role": "assistant", "text": "Gabriela, oi!" if usa else "oi tudo bem?"}
    )

print("\n=== texto da DM (informal, pouca virgula) ===")
CONVERSA = [
    ("oi tudo bem?", False),
    ("vc é muito gata", False),
    ("voce vende conteudo?", True),
    ("quanto custa?", True),
    ("quero sim", False),
]
thread = f"teste-{uuid.uuid4().hex[:8]}"
for texto, as_voice in CONVERSA:
    result = generate_sales_reply(thread, texto, first_name="Gabriela", as_voice=as_voice)
    canal = "AUDIO" if as_voice else "texto"
    virgulas = result.reply.count(",")
    print(f"  [{canal}] {texto}")
    print(f"     -> {result.reply}   (virgulas: {virgulas})")
