import sys

from app.services.sales_agent import generate_sales_reply

sys.stdout.reconfigure(encoding="utf-8")

CASES = [
    ("voce vende conteudo?", True, "Gabriela"),
    ("quanto custa?", True, "Gabriela"),
    ("[a pessoa mandou um áudio]", True, None),
    ("oi tudo bem?", False, "Gabriela"),
]

for text, as_voice, name in CASES:
    result = generate_sales_reply(
        f"teste-voz-{abs(hash(text))}", text, first_name=name, as_voice=as_voice
    )
    canal = "AUDIO" if as_voice else "texto"
    print(f"[{canal}] {text}\n  -> {result.reply}\n")
