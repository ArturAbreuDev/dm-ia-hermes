from __future__ import annotations

import random
from datetime import datetime, time, timedelta, timezone

from app.config import get_settings

# A Vercel não tem tzdata garantido, então fixamos o fuso de Brasília no braço.
_BRASILIA = timezone(timedelta(hours=-3))

# Faixas em que ela está com o celular na mão e responde quase na hora.
_PICO = ((time(11, 30), time(14, 0)), (time(17, 30), time(21, 0)))

# Faixas em que ela está acordada, mas ocupada.
_ATIVA = ((time(8, 0), time(11, 30)), (time(14, 0), time(17, 30)), (time(21, 0), time(23, 30)))


def _janela(agora: time) -> str:
    if any(inicio <= agora < fim for inicio, fim in _PICO):
        return "pico"
    if any(inicio <= agora < fim for inicio, fim in _ATIVA):
        return "ativa"
    return "madrugada"


def reply_delay_seconds(reply: str, is_hot: bool = False, now: datetime | None = None) -> float:
    """Quanto tempo esperar antes de responder, imitando uma pessoa real.

    Soma dois tempos: o de perceber a notificação, que depende da hora do dia, e
    o de escrever ou gravar, que depende do tamanho da resposta.
    """
    settings = get_settings()
    if not settings.reply_delay_enabled:
        return 0.0

    agora = (now or datetime.now(_BRASILIA)).astimezone(_BRASILIA).time()
    janela = _janela(agora)

    if janela == "pico":
        percepcao = random.uniform(1.5, 5.0)
        teto_digitacao = 6.0
    elif janela == "ativa":
        percepcao = random.uniform(8.0, 30.0)
        teto_digitacao = 12.0
    else:
        percepcao = random.uniform(45.0, 110.0)
        teto_digitacao = 18.0

    # Lead quente ela não deixa esfriar: corta o tempo de perceber pela metade.
    if is_hot:
        percepcao *= 0.5

    # Cerca de 4 caracteres por segundo, que é digitação de celular.
    digitacao = min(len(reply) / 4.0, teto_digitacao)

    total = percepcao + digitacao * random.uniform(0.7, 1.3)
    return round(min(total, settings.reply_delay_max_seconds), 1)
