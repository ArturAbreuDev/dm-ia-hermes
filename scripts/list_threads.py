"""Lista as conversas da conta com id, @ e nome, e casa com os alvos pedidos."""

import sys
import unicodedata

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")
S = get_settings()

ALVOS = [a.strip() for a in sys.argv[1:] if a.strip()]


def normal(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn"
    )
    return sem_acento.strip().lower().lstrip("@")


def conversas() -> list[dict]:
    url = f"{S.graph_api_base_url.rstrip('/')}/{S.graph_api_version}/me/conversations"
    pessoas, proxima = [], None
    while True:
        params = {"platform": "instagram", "fields": "participants,updated_time", "limit": 50}
        if proxima:
            params["after"] = proxima
        with httpx.Client(timeout=30) as client:
            corpo = client.get(
                url, params=params,
                headers={"Authorization": f"Bearer {S.instagram_access_token}"},
            ).json()
        if corpo.get("error"):
            print(f"erro: {corpo['error'].get('message')}")
            break
        for thread in corpo.get("data") or []:
            for p in (thread.get("participants") or {}).get("data") or []:
                if p.get("id") and p["id"] != S.instagram_id:
                    pessoas.append(p)
        proxima = ((corpo.get("paging") or {}).get("cursors") or {}).get("after")
        if not proxima or not corpo.get("data"):
            break
    return pessoas


todos = conversas()
print(f"{len(todos)} participantes nas conversas\n")

for p in todos:
    marca = ""
    if ALVOS:
        campos = {normal(p.get("username")), normal(p.get("name"))}
        if any(normal(a) in campos for a in ALVOS):
            marca = "   <<< ALVO"
    if not ALVOS or marca:
        print(f"  {p['id']}  @{p.get('username') or '?'}  |  {p.get('name') or '?'}{marca}")

if ALVOS:
    achados = {
        normal(a)
        for a in ALVOS
        for p in todos
        if normal(a) in {normal(p.get("username")), normal(p.get("name"))}
    }
    faltando = [a for a in ALVOS if normal(a) not in achados]
    if faltando:
        print(f"\nNÃO achei: {faltando}")
