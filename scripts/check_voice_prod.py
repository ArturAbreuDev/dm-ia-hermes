import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://dm-ia-hermes.vercel.app"

with httpx.Client(timeout=90) as client:
    created = client.post(f"{BASE}/v1/voice/preview", json={"text": "oi, tudo bem com você?"})
    print("preview_status", created.status_code)
    if created.status_code != 200:
        print(created.text[:400])
        raise SystemExit(1)
    url = created.json()["audio_url"]
    print("audio_url", url)

    fetched = client.get(url)
    print("fetch_status", fetched.status_code)
    print("content_type", fetched.headers.get("content-type"))
    print("bytes", len(fetched.content))
    print("riff_header", fetched.content[:4])
