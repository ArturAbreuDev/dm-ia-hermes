from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from app.config import get_settings

# A Vercel não tem tzdata garantido, então fixamos o fuso de Brasília no braço.
_BRASILIA = timezone(timedelta(hours=-3))

# Faixas em que ela está com o celular na mão e responde quase na hora.
_PICO = ((time(11, 30), time(14, 0)), (time(17, 30), time(21, 0)))

# Faixas em que ela está acordada, mas ocupada.
_ATIVA = ((time(8, 0), time(11, 30)), (time(14, 0), time(17, 30)), (time(21, 0), time(23, 30)))

# O indicador de "digitando" do Instagram se apaga sozinho depois de uns 20s.
_TETO_DIGITANDO = 15.0


@dataclass
class ReplyPlan:
    """Como a resposta deve ser encenada no tempo.

    Primeiro o silêncio, em que a mensagem fica sem visualizar, como se ela ainda
    não tivesse aberto o app. Depois o "digitando", que só aparece quando ela
    está de fato escrevendo ou gravando.
    """

    silence: float
    typing: float

    @property
    def total(self) -> float:
        return round(self.silence + self.typing, 1)


def _janela(agora: time) -> str:
    if any(inicio <= agora < fim for inicio, fim in _PICO):
        return "pico"
    if any(inicio <= agora < fim for inicio, fim in _ATIVA):
        return "ativa"
    return "madrugada"


def reply_plan(
    reply: str,
    is_hot: bool = False,
    as_voice: bool = False,
    now: datetime | None = None,
) -> ReplyPlan:
    settings = get_settings()
    if not settings.reply_delay_enabled:
        return ReplyPlan(silence=0.0, typing=0.0)

    agora = (now or datetime.now(_BRASILIA)).astimezone(_BRASILIA).time()
    janela = _janela(agora)

    if janela == "pico":
        silencio = random.uniform(1.5, 5.0)
        teto = 6.0
    elif janela == "ativa":
        silencio = random.uniform(8.0, 30.0)
        teto = 12.0
    else:
        silencio = random.uniform(45.0, 110.0)
        teto = _TETO_DIGITANDO

    # Lead quente ela não deixa esfriar: corta o tempo de abrir o app pela metade.
    if is_hot:
        silencio *= 0.5

    if as_voice:
        # Gravar um áudio leva mais tempo do que digitar a mesma frase.
        digitando = min(len(reply) / 12.0 + random.uniform(3.0, 7.0), teto)
    else:
        # Cerca de 4 caracteres por segundo, que é digitação de celular.
        digitando = min(len(reply) / 4.0 * random.uniform(0.7, 1.3), teto)

    sobra = max(settings.reply_delay_max_seconds - digitando, 0.0)
    return ReplyPlan(
        silence=round(min(silencio, sobra), 1),
        typing=round(min(digitando, _TETO_DIGITANDO), 1),
    )
