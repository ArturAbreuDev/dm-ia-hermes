import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://dm-ia-hermes.vercel.app/v1"

with httpx.Client(timeout=120) as client:
    for i in range(3):
        response = client.post(
            f"{BASE}/simulate",
            json={"sender_id": f"teste-expointer-{i}", "text": "voce foi na expointer né?"},
        )
        print(response.status_code, "->", response.json().get("reply"))
