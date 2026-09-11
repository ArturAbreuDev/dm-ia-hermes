import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://dm-ia-hermes.vercel.app"
RECIPIENT = "1420122640048360"
TEXT = "Gabriela, tenho sim, quer que eu te explique as opções?"

with httpx.Client(timeout=180) as client:
    response = client.post(
        f"{BASE}/v1/voice/send",
        json={"recipient_id": RECIPIENT, "text": TEXT},
    )
    print("send status", response.status_code)
    print(response.text.replace("\\/", "/")[:400])

    if response.status_code == 200:
        url = response.json()["audio_url"]
        head = client.head(url)
        print("HEAD", head.status_code, head.headers.get("content-type"), head.headers.get("content-length"))
