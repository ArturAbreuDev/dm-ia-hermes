"""Resolve alvos por @ ou por nome, buscando o perfil de cada conversa."""

import sys
import unicodedata

import httpx

from app.config import get_settings
from app.services.instagram import get_user_profile

sys.stdout.reconfigure(encoding="utf-8")
S = get_settings()
ALVOS = [a.strip() for a in sys.argv[1:] if a.strip()]


def normal(texto: str) -> str:
    sem = "".join(
        c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn"
    )
    return " ".join(sem.strip().lower().lstrip("@").split())


def participantes() -> list[str]:
    url = f"{S.graph_api_base_url.rstrip('/')}/{S.graph_api_version}/me/conversations"
    ids, proxima = [], None
    while True:
        params = {"platform": "instagram", "fields": "participants", "limit": 50}
        if proxima:
            params["after"] = proxima
        with httpx.Client(timeout=30) as client:
            corpo = client.get(
                url, params=params,
                headers={"Authorization": f"Bearer {S.instagram_access_token}"},
            ).json()
        if corpo.get("error"):
            break
        for thread in corpo.get("data") or []:
            for p in (thread.get("participants") or {}).get("data") or []:
                if p.get("id") and p["id"] != S.instagram_id and p["id"] not in ids:
                    ids.append(p["id"])
        proxima = ((corpo.get("paging") or {}).get("cursors") or {}).get("after")
        if not proxima:
            break
    return ids


achados: dict[str, tuple[str, str]] = {}
for igsid in participantes():
    perfil = get_user_profile(igsid)
    username, nome = perfil.get("username") or "", perfil.get("name") or ""
    campos = {normal(username), normal(nome)}
    alvo = next((a for a in ALVOS if normal(a) in campos), None)
    marca = "   <<< ALVO" if alvo else ""
    print(f"  {igsid}  @{username or '?'}  |  {nome or '?'}{marca}")
    if alvo:
        achados[alvo] = (igsid, username or nome)

print("\nresolvidos:")
for alvo, (igsid, quem) in achados.items():
    print(f"  {alvo:32} -> {igsid}  ({quem})")
faltando = [a for a in ALVOS if a not in achados]
if faltando:
    print(f"\nNÃO achei: {faltando}")
