import sys

from app.config import get_settings
from app.services.sales_agent import generate_sales_reply
from app.store import memory

sys.stdout.reconfigure(encoding="utf-8")
get_settings.cache_clear()

CONVERSATIONS = [
    ["gata"],
    ["oi tudo bem", "vc é linda demais", "tem mais foto?"],
    ["quanto é?"],
    ["asdasdasd"],
    ["quero agora manda o link"],
    ["não quero nada, obrigado"],
]

for index, turns in enumerate(CONVERSATIONS):
    sender = f"teste-{index}"
    print(f"\n--- conversa {index + 1} ---")
    for text in turns:
        memory.save_message(sender, "user", text)
        result = generate_sales_reply(sender, text)
        print(f"cliente: {text}")
        if result.should_send:
            memory.save_message(sender, "assistant", result.reply)
            print(f"livia:   {result.reply}")
        else:
            print("livia:   (não responde)")
