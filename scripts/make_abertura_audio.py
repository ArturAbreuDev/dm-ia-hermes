"""Gera o áudio de abertura em arquivo, para ouvir antes de soltar em produção."""

from __future__ import annotations

import sys
from pathlib import Path

from app.services import canned, elevenlabs, voice, voice_director

sys.stdout.reconfigure(encoding="utf-8")

NOMES = [n for n in sys.argv[1:]] or ["Rafael", None]
DESTINO = Path("relatorios/audios")
DESTINO.mkdir(parents=True, exist_ok=True)

for nome in NOMES:
    item = canned.abertura(nome)
    print(f"\n{nome or '(sem nome)'}:")
    print(f"  texto: {item.texto}")

    # O mesmo tratamento que o áudio recebe em produção: tirar o que não se fala
    # e passar pela direção de voz, senão o arquivo aqui sairia diferente do real.
    falado = voice_director.direct_for_speech(voice._strip_for_speech(item.texto))
    if falado != item.texto:
        print(f"  falado: {falado}")

    clip = elevenlabs.synthesize(falado)
    if not clip:
        print("  ERRO: a ElevenLabs não devolveu áudio (confira a chave e a voz)")
        continue
    arquivo = DESTINO / f"abertura-{(nome or 'amor').lower()}.{clip.extension}"
    arquivo.write_bytes(clip.data)
    print(f"  arquivo: {arquivo.resolve()}  ({len(clip.data) / 1024:.0f} KB, {clip.mime})")
