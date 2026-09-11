import sys
import uuid

from app.services.sales_agent import generate_sales_reply

sys.stdout.reconfigure(encoding="utf-8")

CASOS = [
    ("story marcando", "[a pessoa te marcou no story dela: um print do seu perfil escrito 'vejam ela']", True, False),
    ("audio transcrito", '[a pessoa mandou um áudio dizendo] "oi gata, tudo bem? queria te conhecer melhor"', True, True),
    ("audio sobre venda", '[a pessoa mandou um áudio dizendo] "você vende conteúdo?"', True, True),
    ("audio ilegivel", "[a pessoa mandou um áudio e você não conseguiu ouvir]", True, True),
    ("foto", "[a pessoa mandou uma foto: uma selfie dele no carro]", True, False),
    ("video", "[a pessoa mandou um vídeo]", True, False),
    ("coracao", "[a pessoa reagiu com um coração]", True, False),
]

for nome, texto, must_reply, is_audio in CASOS:
    result = generate_sales_reply(
        f"mid-{uuid.uuid4().hex[:8]}",
        texto,
        first_name="Gabriela",
        as_voice=is_audio,
        must_reply=must_reply,
    )
    canal = "AUDIO" if is_audio else "texto"
    resposta = result.reply or f"<<SILENCIO intent={result.intent}>>"
    print(f"[{canal}] {nome}")
    print(f"   -> {resposta}\n")
