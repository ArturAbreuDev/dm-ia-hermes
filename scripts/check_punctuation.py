import sys
from datetime import datetime, timedelta, timezone

from app.services.timing import reply_delay_seconds
from app.services.voice import _strip_for_speech
from app.services.voice_director import direct_for_speech

sys.stdout.reconfigure(encoding="utf-8")

BR = timezone(timedelta(hours=-3))

print("=== pontuacao + diretor de voz ===")
FALAS = [
    "Gabriela, tenho sim 😏 quer que eu te explique as opções?",
    "kkkk vc é engraçado, tenho pack de R$ 10, 20 e 30",
    "tenho sim.... mas pq vc quer saber?",
]
for fala in FALAS:
    limpo = _strip_for_speech(fala)
    print(f"  original: {fala}")
    print(f"   limpeza: {limpo}")
    print(f"   diretor: {direct_for_speech(limpo)!r}\n")

print("=== delay por horario ===")
REPLY = "Gabriela, tenho sim, quer que eu te explique as opções?"
for hora in [0, 3, 9, 12, 15, 18, 20, 22]:
    agora = datetime(2026, 9, 11, hora, 0, tzinfo=BR)
    frio = reply_delay_seconds(REPLY, is_hot=False, now=agora)
    quente = reply_delay_seconds(REPLY, is_hot=True, now=agora)
    print(f"  {hora:02d}h -> normal {frio:>6}s | lead quente {quente:>6}s")
