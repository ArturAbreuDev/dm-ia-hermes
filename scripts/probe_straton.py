"""Descobre onde vive a StratonBot antes de eu chutar qualquer endpoint."""

from __future__ import annotations

import socket
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

CANDIDATOS = [
    "stratonbot.com",
    "www.stratonbot.com",
    "stratonbot.com.br",
    "stratonbot.io",
    "stratonbot.app",
    "stratonbot.net",
    "straton.bot",
    "docs.stratonbot.com",
    "api.stratonbot.com",
    "app.stratonbot.com",
    "dash.stratonbot.com",
    "painel.stratonbot.com",
    "botgram.club",
]

for host in CANDIDATOS:
    try:
        ip = socket.gethostbyname(host)
    except OSError as erro:
        print(f"  {host:<28} DNS não resolve ({erro.strerror or erro})")
        continue
    status = ""
    try:
        r = httpx.get(f"https://{host}", timeout=15, follow_redirects=True)
        titulo = ""
        if "text/html" in r.headers.get("content-type", ""):
            corpo = r.text
            inicio = corpo.lower().find("<title")
            if inicio != -1:
                fim = corpo.find("</title", inicio)
                titulo = corpo[corpo.find(">", inicio) + 1 : fim].strip()[:80]
        status = f"HTTP {r.status_code} -> {r.url}  {titulo!r}"
    except Exception as erro:  # noqa: BLE001
        status = f"erro no https: {type(erro).__name__}: {erro}"
    print(f"  {host:<28} {ip:<16} {status}")
