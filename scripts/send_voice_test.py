import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://dm-ia-hermes.vercel.app"
RECIPIENT = "1420122640048360"
TEXT = "oi, tudo bem?"

FORMATS = ["pcm_24000", "pcm_16000", "pcm_44100", "ulaw_8000", "opus_48000_128"]

with httpx.Client(timeout=120) as client:
    for output_format in FORMATS:
        response = client.post(
            f"{BASE}/v1/voice/send",
            json={"recipient_id": RECIPIENT, "text": TEXT, "output_format": output_format},
        )
        body = response.text.replace("\\/", "/")
        if response.status_code == 200:
            print(f"{output_format:<16} OK   {body[:120]}")
            break
        marker = "message" if "message" in body else ""
        print(f"{output_format:<16} {response.status_code}  {body[:200]}")
