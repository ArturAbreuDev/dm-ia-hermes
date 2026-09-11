import sys
import time

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")

RECIPIENT = "1420122640048360"
settings = get_settings()

for action in ["mark_seen", "typing_on", "typing_off"]:
    response = httpx.post(
        settings.graph_messages_url,
        params={"access_token": settings.instagram_access_token},
        headers={"Content-Type": "application/json"},
        json={"recipient": {"id": RECIPIENT}, "sender_action": action},
        timeout=30,
    )
    print(f"{action:<12} {response.status_code} {response.text[:220]}")
    time.sleep(1)
