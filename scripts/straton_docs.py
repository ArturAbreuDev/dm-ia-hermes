"""Extrai a referência da API da StratonBot de dentro do bundle do painel.

A documentação vive num painel que só renderiza no navegador, então o caminho
honesto para ler o que existe de verdade é ir nos arquivos JS que o painel
carrega e recolher as rotas e os textos de documentação que estão ali.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://stratonbot.app"
DESTINO = Path("tmp/straton")
DESTINO.mkdir(parents=True, exist_ok=True)

cliente = httpx.Client(timeout=60, follow_redirects=True)
pagina = cliente.get(f"{BASE}/api")
print(f"GET /api -> {pagina.status_code}, {len(pagina.text)} bytes")

scripts = sorted(set(re.findall(r'src="(/_next/static/[^"]+\.js)"', pagina.text)))
# O manifesto do Next lista chunks que a página só busca depois; entram também.
scripts += sorted(set(re.findall(r'"(/_next/static/chunks/[^"]+\.js)"', pagina.text)))
scripts = sorted(set(scripts))
print(f"{len(scripts)} arquivos js referenciados\n")

ROTA = re.compile(r'["\'`](/api/v\d[a-zA-Z0-9/_\-{}:.$]*)["\'`]')
achadas: dict[str, set[str]] = {}
for caminho in scripts:
    try:
        resposta = cliente.get(f"{BASE}{caminho}")
    except Exception as erro:  # noqa: BLE001
        print(f"  falhou {caminho}: {erro}")
        continue
    if resposta.status_code != 200:
        continue
    nome = caminho.rsplit("/", 1)[-1]
    (DESTINO / nome).write_text(resposta.text, encoding="utf-8", errors="replace")
    for rota in ROTA.findall(resposta.text):
        achadas.setdefault(rota, set()).add(nome)

print(f"{len(achadas)} rotas /api/vN encontradas:\n")
for rota in sorted(achadas):
    print(f"  {rota}")
print(f"\nbundles salvos em {DESTINO.resolve()}")
