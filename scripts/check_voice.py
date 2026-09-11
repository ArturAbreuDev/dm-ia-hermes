import json
import sys

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")
get_settings.cache_clear()
settings = get_settings()

url = f"https://api.elevenlabs.io/v1/voices/{settings.elevenlabs_voice_id}"
with httpx.Client(timeout=30) as client:
    response = client.get(url, headers={"xi-api-key": settings.elevenlabs_api_key})
    print("status", response.status_code)
    data = response.json()

print("name", data.get("name"))
print("category", data.get("category"))
print("labels", json.dumps(data.get("labels") or {}, ensure_ascii=False))
print("description", (data.get("description") or "")[:200])
