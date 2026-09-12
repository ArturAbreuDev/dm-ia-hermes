"""Áudios prontos que ela manda em momentos previsíveis.

Explicar o fluxo é sempre a mesma explicação, então não vale pedir para a IA
escrever de novo a cada vez: além de gastar, é onde ela já errou antes. O texto
é fixo, e o áudio é gerado uma vez e reaproveitado.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from app.config import get_settings
from app.services import elevenlabs, voice, voice_director
from app.store import media

logger = logging.getLogger(__name__)

# Como funciona, do começo ao fim. Vai junto quando o link sai.
FLUXO_GERAL = (
    "oi amor, deixa eu te explicar como funciona que é bem simples. "
    "você entra no meu link, e é ali dentro que você escolhe o plano que quiser. "
    "assim que você escolhe e paga, você já cai direto no grupo, na hora. "
    "e quanto maior o plano, mais coisinha você vai encontrar lá dentro. "
    "é só isso, sem complicação nenhuma."
)

# Para quem abriu o link e estranhou não ter caído no Telegram na hora.
FLUXO_DUVIDA = (
    "amor, aquela página que você abriu tá certinha, é ali mesmo que você escolhe o plano. "
    "o link não te joga no telegram direto, ele te leva pra escolher primeiro. "
    "você escolhe o plano ali, faz o pagamento, e aí sim você cai direto no grupo. "
    "e quanto maior o plano, mais coisinha tem lá dentro. "
    "pode ir tranquilo que tá tudo certo."
)


@dataclass
class Canned:
    nome: str
    texto: str
    campo: str  # marca no lead, para não repetir com a mesma pessoa


GERAL = Canned("fluxo_geral", FLUXO_GERAL, "audio_fluxo_geral")
DUVIDA = Canned("fluxo_duvida", FLUXO_DUVIDA, "audio_fluxo_duvida")


def pick(reply: str, flags, lead: dict) -> Canned | None:
    """Qual áudio pronto cabe agora, se algum."""
    settings = get_settings()
    if not settings.canned_audio_enabled or not settings.voice_ready:
        return None

    flags = flags or frozenset()
    quer_entender = bool({"duvida_fluxo", "como_funciona"} & flags)

    # Qual dos dois cabe depende de ele já ter o link ou não. O áudio de dúvida
    # começa dizendo "aquela página que você abriu": mandar isso para quem nunca
    # recebeu o link é falar de uma tela que ele não viu. Quem pergunta como
    # funciona antes do link precisa da explicação do começo.
    if quer_entender and lead.get("link_sent") and not lead.get(DUVIDA.campo):
        return DUVIDA
    if quer_entender and not lead.get(GERAL.campo):
        return GERAL

    checkout = settings.checkout_url
    if checkout and checkout in (reply or "") and not lead.get(GERAL.campo):
        return GERAL

    return None


def url_for(item: Canned) -> str | None:
    """URL do áudio, gerando só se ainda não existir."""
    settings = get_settings()
    assinatura = "|".join(
        [item.texto, settings.elevenlabs_voice_id, settings.elevenlabs_model,
         settings.elevenlabs_output_format]
    )
    clip_id = hashlib.sha256(assinatura.encode()).hexdigest()[:32]

    guardado = media.get_audio(clip_id)
    if guardado:
        extensao = "wav" if "wav" in guardado[1] else "mp3"
        return f"{settings.base_url}/media/audio/{clip_id}.{extensao}"

    falado = voice_director.direct_for_speech(voice._strip_for_speech(item.texto))
    clip = elevenlabs.synthesize(falado)
    if not clip:
        logger.warning("Não consegui gerar o áudio pronto %s", item.nome)
        return None
    media.save_audio_with_id(clip_id, clip.data, clip.mime)
    logger.info("Áudio pronto %s gerado e guardado como %s", item.nome, clip_id)
    return f"{settings.base_url}/media/audio/{clip_id}.{clip.extension}"
