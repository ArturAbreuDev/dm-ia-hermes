import json
import sys

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")

settings = get_settings()
base = f"{settings.graph_api_base_url.rstrip('/')}/{settings.graph_api_version}"
token = settings.instagram_access_token

with httpx.Client(timeout=30) as client:
    print("--- quem sou eu ---")
    me = client.get(f"{base}/me", params={"fields": "id,user_id,username", "access_token": token})
    print(me.status_code, me.text[:300])
    print(f"\ninstagram_id usado para enviar: {settings.instagram_id}\n")

    print("--- conversas abertas ---")
    conv = client.get(
        f"{base}/me/conversations",
        params={
            "fields": "id,updated_time,participants",
            "access_token": token,
            "limit": "10",
        },
    )
    print(conv.status_code)
    try:
        data = conv.json()
    except ValueError:
        print(conv.text[:400])
        raise SystemExit

    for item in data.get("data", []):
        gente = [
            f"{p.get('username', '?')}={p.get('id')}"
            for p in (item.get("participants") or {}).get("data", [])
        ]
        print(f"  {item.get('updated_time')}  {' | '.join(gente)}")
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False)[:500])
