import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://dm-ia-hermes.vercel.app"
SENHA = "iow80pgq1e"

with httpx.Client(timeout=60, follow_redirects=True) as client:
    sem_senha = client.get(f"{BASE}/diario")
    print("sem senha      ->", sem_senha.status_code, "tela de login" if "password" in sem_senha.text else "?")

    errada = client.get(f"{BASE}/diario", params={"k": "errada"})
    print("senha errada   ->", errada.status_code)

    ok = client.get(f"{BASE}/diario", params={"k": SENHA})
    print("senha certa    ->", ok.status_code, "| Expointer na lista:", "Expointer" in ok.text)

    criou = client.post(
        f"{BASE}/diario",
        data={"k": SENHA, "texto": "tomei açaí na praia com as amigas"},
    )
    print("criou nota     ->", criou.status_code, "| acento ok:", "açaí" in criou.text)

    itens = client.get(f"{BASE}/v1/context").json()["itens"]
    print("no contexto    ->", [i["description"] for i in itens])

    alvo = next((i["id"] for i in itens if "açaí" in i["description"]), None)
    if alvo:
        apagou = client.post(f"{BASE}/diario/apagar", data={"k": SENHA, "id": alvo})
        print("apagou         ->", apagou.status_code, "| saiu da lista:", "açaí" not in apagou.text)
