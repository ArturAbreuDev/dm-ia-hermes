import sys
from datetime import datetime, timedelta, timezone

from app.services.timing import reply_plan
from app.services.voice import _HOT_PATTERNS, _strip_for_speech

sys.stdout.reconfigure(encoding="utf-8")

BR = timezone(timedelta(hours=-3))

print("=== gatilho de audio (so palavra forte) ===")
MENSAGENS = [
    ("voce vende conteudo?", True),
    ("quanto custa?", True),
    ("tem pack?", True),
    ("quero comprar", True),
    ("como funciona?", True),
    ("oi tudo bem?", False),
    ("quero te conhecer", False),
    ("me manda o link", False),
    ("que foto linda", False),
    ("vc é muito gata", False),
]
for msg, esperado in MENSAGENS:
    achou = bool(_HOT_PATTERNS.search(msg))
    status = "ok " if achou == esperado else "ERRO"
    print(f"  [{status}] audio={str(achou):<5} {msg}")

print("\n=== giria expandida para o audio ===")
for fala in ["mt bom nsei se vou", "sla, tbm quero ss", "td bem? vdd q vc é gata"]:
    print(f"  {fala!r} -> {_strip_for_speech(fala)!r}")

print("\n=== plano de tempo (silencio + digitando) ===")
REPLY = "tenho simm quer que eu te explique?"
for hora in [3, 9, 12, 18, 22]:
    agora = datetime(2026, 9, 11, hora, 0, tzinfo=BR)
    texto = reply_plan(REPLY, is_hot=False, as_voice=False, now=agora)
    audio = reply_plan(REPLY, is_hot=True, as_voice=True, now=agora)
    print(
        f"  {hora:02d}h texto: {texto.silence:>5}s + {texto.typing:>4}s = {texto.total:>5}s"
        f" | audio quente: {audio.silence:>5}s + {audio.typing:>4}s = {audio.total:>5}s"
    )
