"""Dispara o link e o áudio do fluxo para uma lista de @ do Instagram."""

import sys

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://dm-ia-hermes.vercel.app"

ALVOS = {
    "1619917019592924": "mulekinho__244",
    "1394489339549598": "joao_phedrolima",
    "1074616748623948": "duduoliveira_020",
}

chave = get_settings().diary_password
resposta = httpx.post(
    f"{BASE}/v1/outreach/flow",
    params={"k": chave},
    json={"igsids": list(ALVOS)},
    timeout=280,
)
print("HTTP", resposta.status_code)
corpo = resposta.json()
print("audio:", corpo.get("audio_url"))
for item in corpo.get("resultados", []):
    quem = ALVOS.get(item["igsid"], item["igsid"])
    print(f"  @{quem:24} texto={item.get('texto')}  audio={item.get('audio')}")
