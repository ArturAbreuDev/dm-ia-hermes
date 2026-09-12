"""Consulta o perfil de cada contato e mostra o erro cru quando falha.

Perfil que não carrega é indício de conta apagada, desativada ou que bloqueou
o perfil. O código de erro do Instagram é o que diz qual dos três é.
"""

from __future__ import annotations

import sys

import httpx

from app.config import get_settings
from app.store import memory

sys.stdout.reconfigure(encoding="utf-8")
S = get_settings()

IGSIDS = sys.argv[1:]
if not IGSIDS:
    IGSIDS = sorted({m["sender_id"] for m in memory.message_activity(days=7)})

url_base = f"{S.graph_api_base_url.rstrip('/')}/{S.graph_api_version}"
falhas = 0

for igsid in IGSIDS:
    with httpx.Client(timeout=20) as client:
        resposta = client.get(
            f"{url_base}/{igsid}",
            params={"fields": "name,username"},
            headers={"Authorization": f"Bearer {S.instagram_access_token}"},
        )
    corpo = resposta.json()
    if resposta.status_code == 200 and not corpo.get("error"):
        print(f"  ok    {igsid:18} @{corpo.get('username') or '?'}")
        continue

    falhas += 1
    erro = corpo.get("error") or {}
    print(
        f"  FALHA {igsid:18} http={resposta.status_code} "
        f"code={erro.get('code')} subcode={erro.get('error_subcode')} "
        f"type={erro.get('type')}\n         {erro.get('message')}"
    )

print(f"\n{falhas} de {len(IGSIDS)} perfis não carregam")
