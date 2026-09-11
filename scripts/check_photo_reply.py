import sys
import uuid

from app.services import engagement
from app.services.sales_agent import generate_sales_reply
from app.store import memory

sys.stdout.reconfigure(encoding="utf-8")

# O que o incoming.read() entrega depois de olhar a mídia com o vision.
FOTOS = [
    "[a pessoa mandou uma foto: um homem de uns 30 anos, sem camisa, "
    "tirando selfie no espelho de uma academia, com fone de ouvido no pescoço]",
    "[a pessoa mandou uma foto: um cachorro golden retriever dormindo "
    "em cima de um sofá cinza]",
    "[a pessoa mandou uma foto: um prato de churrasco com arroz, "
    "farofa e uma lata de cerveja do lado]",
    "[a pessoa mandou uma foto: uma praia ao anoitecer, com o céu laranja "
    "e algumas pessoas caminhando na areia]",
]

for descricao in FOTOS:
    thread = f"foto-{uuid.uuid4().hex[:8]}"
    stance = engagement.decide(memory.get_lead(thread), descricao, False)
    result = generate_sales_reply(
        thread, descricao, first_name="Bruno", stance=stance, must_reply=True
    )
    print(f"  > {descricao}")
    print(f"    {result.reply or '<<silencio>>'}\n")
