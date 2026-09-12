"""Confere a tela de bloqueio já publicada, sem escrever nada."""

from __future__ import annotations

import re
import sys

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")

pagina = httpx.get(
    "https://dm-ia-hermes.vercel.app/diario",
    params={"k": get_settings().diary_password},
    timeout=120,
)
print("HTTP", pagina.status_code)
print("seção existe:", "Não responder" in pagina.text)
print("bloqueados na lista:", re.findall(r'class="txt arroba">([^<]+)<', pagina.text))
