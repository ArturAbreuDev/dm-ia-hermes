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


def _preco() -> str:
    return get_settings().active_price_spoken()


def _tem_varios_planos() -> bool:
    return "ou" in get_settings().active_price()


# Como funciona, do começo ao fim. Vai junto quando o link sai.
def _fluxo_geral() -> str:
    if _tem_varios_planos():
        return (
            "é simples. entra no link, escolhe o plano, "
            + _preco()
            + ", paga e cai no grupo na hora. "
            "quanto maior o plano, mais coisa tem. "
            "é isso."
        )
    return (
        "é simples. entra no link, paga "
        + _preco()
        + " e cai no grupo na hora. "
        "é isso."
    )


# Para quem abriu o link e estranhou não ter caído no Telegram na hora.
def _fluxo_duvida() -> str:
    if _tem_varios_planos():
        return (
            "aquela página tá certa. o link não joga no telegram direto, "
            "é pra escolher o plano primeiro. "
            "escolhe entre "
            + _preco()
            + ", paga, e aí cai no grupo. "
            "não tem outro caminho."
        )
    return (
        "aquela página tá certa. o link não joga no telegram direto, "
        "é pra pagar primeiro. "
        "paga "
        + _preco()
        + " ali e cai no grupo. "
        "não tem outro caminho."
    )


# Para quem chega na primeira mensagem já elogiando ou já falando de sexo. Diz o
# nome da pessoa, diz onde é o lugar reservado e diz o que fazer. Nada de pergunta.
ABERTURA = (
    "{nome}. "
    "aqui no instagram eu não mostro quase nada. "
    "o conteúdo tá no telegram. "
    "{cta}"
)


@dataclass
class Canned:
    nome: str
    texto: str
    campo: str  # marca no lead, para não repetir com a mesma pessoa


def geral() -> Canned:
    return Canned("fluxo_geral", _fluxo_geral(), "audio_fluxo_geral")


def duvida() -> Canned:
    return Canned("fluxo_duvida", _fluxo_duvida(), "audio_fluxo_duvida")


# Compatível com `is canned.GERAL` nos testes: o objeto muda o texto a cada
# leitura via propriedade, mas a identidade do proxy permanece.
class _CannedAoVivo:
    def __init__(self, nome: str, campo: str, montar) -> None:
        self.nome = nome
        self.campo = campo
        self._montar = montar

    @property
    def texto(self) -> str:
        return self._montar()


GERAL = _CannedAoVivo("fluxo_geral", "audio_fluxo_geral", _fluxo_geral)
DUVIDA = _CannedAoVivo("fluxo_duvida", "audio_fluxo_duvida", _fluxo_duvida)


def abertura(primeiro_nome: str | None) -> Canned:
    """O áudio de chegada, com o nome de quem mandou a mensagem.

    O nome entra no texto, então cada nome vira um clipe próprio. Isso é de
    propósito: `url_for` guarda o áudio pela assinatura do texto, então o mesmo
    nome só é gerado uma vez e depois é reaproveitado por todo mundo que se chama
    assim. Sem nome ela fala "amor", que é como ela chamaria alguém mesmo.
    """
    nome = (primeiro_nome or "").strip() or "amor"
    if _tem_varios_planos():
        cta = (
            f"escolhe o plano, {_preco()}, "
            "e já é encaminhado pra dentro."
        )
    else:
        cta = f"paga {_preco()} e já é encaminhado pra dentro."
    return Canned(
        "abertura",
        ABERTURA.format(nome=nome.lower(), cta=cta),
        "audio_abertura",
    )


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

    # Qualquer um dos dois links conta: a troca no /diario não pode deixar
    # o áudio de fluxo sem sair.
    for url in settings.all_checkout_urls():
        if url and url in (reply or "") and not lead.get(GERAL.campo):
            return GERAL

    return None


def url_for(item: Canned | _CannedAoVivo) -> str | None:
    """URL do áudio, gerando só se ainda não existir."""
    settings = get_settings()
    texto = item.texto
    assinatura = "|".join(
        [
            texto,
            settings.elevenlabs_voice_id,
            settings.elevenlabs_model,
            settings.elevenlabs_output_format,
        ]
    )
    clip_id = hashlib.sha256(assinatura.encode()).hexdigest()[:32]

    guardado = media.get_audio(clip_id)
    if guardado:
        extensao = "wav" if "wav" in guardado[1] else "mp3"
        return f"{settings.base_url}/media/audio/{clip_id}.{extensao}"

    falado = voice_director.direct_for_speech(voice._strip_for_speech(texto))
    clip = elevenlabs.synthesize(falado)
    if not clip:
        logger.warning("Não consegui gerar o áudio pronto %s", item.nome)
        return None
    media.save_audio_with_id(clip_id, clip.data, clip.mime)
    logger.info("Áudio pronto %s gerado e guardado como %s", item.nome, clip_id)
    return f"{settings.base_url}/media/audio/{clip_id}.{clip.extension}"
