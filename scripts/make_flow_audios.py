"""Gera os áudios de explicação do fluxo, em arquivo, para escutar antes de enviar."""

import sys
from pathlib import Path

from app.services import elevenlabs, voice, voice_director

sys.stdout.reconfigure(encoding="utf-8")

DESTINO = Path("audios")
DESTINO.mkdir(exist_ok=True)

GENERICO = (
    "oi amor, deixa eu te explicar como funciona que é bem simples. "
    "você entra no meu link, e é ali dentro que você escolhe o plano que quiser. "
    "assim que você escolhe e paga, você já cai direto no grupo, na hora. "
    "e quanto maior o plano, mais coisinha você vai encontrar lá dentro. "
    "é só isso, sem complicação nenhuma."
)

ESPECIFICO = (
    "amor, acho que eu me confundi ali, foi mal. "
    "aquela página que você abriu tá certinha, é ali mesmo que você escolhe o plano. "
    "o link não te joga no telegram direto, ele te leva pra escolher primeiro. "
    "você escolhe o plano ali, faz o pagamento, e aí sim você cai direto no grupo. "
    "e quanto maior o plano, mais coisinha tem lá dentro. "
    "pode ir tranquilo que tá tudo certo."
)


def gerar(nome: str, texto: str) -> None:
    print(f"\n{'=' * 70}\n{nome}\n{'=' * 70}")
    print(f"escrito:\n  {texto}\n")
    falado = voice_director.direct_for_speech(voice._strip_for_speech(texto))
    print(f"dirigido para a voz:\n  {falado}\n")

    for formato in ("mp3_44100_128", "pcm_24000"):
        clip = elevenlabs.synthesize(falado, output_format=formato)
        if not clip:
            print(f"  FALHOU em {formato}")
            continue
        arquivo = DESTINO / f"{nome}.{clip.extension}"
        arquivo.write_bytes(clip.data)
        print(f"  {arquivo}  ({len(clip.data) / 1024:.0f} KB, {clip.mime})")


gerar("fluxo-generico", GENERICO)
gerar("fluxo-puto100vergonha", ESPECIFICO)
print(f"\npasta: {DESTINO.resolve()}")
