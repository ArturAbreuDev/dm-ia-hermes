import sys

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")
get_settings.cache_clear()
settings = get_settings()
headers = {"Authorization": f"Bearer {settings.instagram_access_token}"}
base = "https://graph.instagram.com/v25.0"

with httpx.Client(timeout=20) as client:
    me = client.get(f"{base}/me", params={"fields": "id,username"}, headers=headers)
    print("me_status", me.status_code)
    data = me.json()
    print("username", data.get("username"))
    print("id", data.get("id"))
    conv = client.get(
        f"{base}/me/conversations",
        params={"platform": "instagram", "limit": 5},
        headers=headers,
    )
    payload = conv.json()
    print("conv_status", conv.status_code)
    print("count", len(payload.get("data") or []))
    err = payload.get("error") or {}
    if err:
        print("err", err.get("message"))
