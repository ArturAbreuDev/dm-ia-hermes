"""Descobre o IGSID de um @ do Instagram entre quem já mandou DM."""

import sys

import httpx

from app.config import get_settings
from app.services.instagram import get_user_profile
from app.store.memory import _postgres, _postgres_dsn, _sqlite

sys.stdout.reconfigure(encoding="utf-8")
S = get_settings()

procurado = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lstrip("@").lower()
if not procurado:
    raise SystemExit("uso: python -m scripts.find_igsid <username>")


def conhecidos() -> list[str]:
    dsn = _postgres_dsn()
    if dsn:
        with _postgres(dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT sender_id, max(id) FROM messages GROUP BY sender_id"
                " ORDER BY max(id) DESC"
            )
            return [linha[0] for linha in cur.fetchall()]
    with _sqlite() as conn:
        linhas = conn.execute(
            "SELECT sender_id FROM messages GROUP BY sender_id ORDER BY max(id) DESC"
        ).fetchall()
    return [linha["sender_id"] for linha in linhas]


# As conversas da conta também servem, e pegam quem não está no nosso banco.
def das_conversas() -> list[str]:
    if not (S.instagram_access_token and S.instagram_id):
        return []
    url = f"{S.graph_api_base_url.rstrip('/')}/{S.graph_api_version}/me/conversations"
    try:
        with httpx.Client(timeout=30) as client:
            corpo = client.get(
                url,
                params={"platform": "instagram", "fields": "participants", "limit": 100},
                headers={"Authorization": f"Bearer {S.instagram_access_token}"},
            ).json()
    except httpx.HTTPError as erro:
        print(f"  (me/conversations falhou: {erro})")
        return []
    if corpo.get("error"):
        print(f"  (me/conversations recusado: {corpo['error'].get('message')})")
        return []
    encontrados = []
    for thread in corpo.get("data") or []:
        for p in (thread.get("participants") or {}).get("data") or []:
            username = (p.get("username") or "").lower()
            if p.get("id") and p["id"] != S.instagram_id:
                encontrados.append(p["id"])
                if username == procurado:
                    print(f"\nACHEI nas conversas: @{p['username']} -> {p['id']}")
    return encontrados


print(f"procurando @{procurado}")
alvos = das_conversas()

vistos = set(alvos)
for igsid in conhecidos():
    if igsid in vistos:
        continue
    vistos.add(igsid)
    perfil = get_user_profile(igsid)
    username = (perfil.get("username") or "").lower()
    marca = "  <<< ACHEI" if username == procurado else ""
    print(f"  {igsid}  @{perfil.get('username') or '?'}  {perfil.get('name') or ''}{marca}")
