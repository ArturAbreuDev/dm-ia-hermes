import os
import sys

import httpx
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

KEY = os.environ["ELEVENLABS_API_KEY"]
VOICE = "TiWo3FueJZwAK0CaHsYV"
TEXT = "Oi Gabriela, tenho sim... quer que eu te explique as opções?"

for model in ["eleven_v3", "eleven_v3_conversational"]:
    for fmt in ["pcm_24000", "pcm_44100", "mp3_44100_128"]:
        try:
            response = httpx.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}",
                params={"output_format": fmt},
                headers={"xi-api-key": KEY, "Content-Type": "application/json"},
                json={"text": TEXT, "model_id": model},
                timeout=90,
            )
        except httpx.HTTPError as exc:
            print(f"{model:<26} {fmt:<14} ERRO {exc}")
            continue
        detail = "" if response.status_code == 200 else response.text[:160]
        print(f"{model:<26} {fmt:<14} {response.status_code} {len(response.content)}b {detail}")
