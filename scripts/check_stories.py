import json
import sys

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")

settings = get_settings()
base = f"{settings.graph_api_base_url.rstrip('/')}/{settings.graph_api_version}"
token = settings.instagram_access_token

TENTATIVAS = [
    ("/me/stories", {"fields": "id,media_type,media_url,permalink,timestamp,caption"}),
    (f"/{settings.instagram_id}/stories", {"fields": "id,media_type,media_url,timestamp,caption"}),
    ("/me/media", {"fields": "id,media_type,caption,timestamp", "limit": "3"}),
    ("/me", {"fields": "id,username,name,biography"}),
]

with httpx.Client(timeout=30) as client:
    for path, params in TENTATIVAS:
        response = client.get(
            f"{base}{path}", params={**params, "access_token": token}
        )
        print(f"--- GET {path} -> {response.status_code}")
        try:
            print(json.dumps(response.json(), ensure_ascii=False)[:700])
        except ValueError:
            print(response.text[:400])
        print()
