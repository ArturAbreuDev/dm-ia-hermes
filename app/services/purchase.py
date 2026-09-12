"""Confirmar compra pelo grupo do Telegram.

O Botgram não avisa ninguém quando alguém paga, mas ele coloca o comprador no
grupo. Então estar no grupo é a prova. O problema é ligar isso ao Instagram:
são duas identidades diferentes, e a Bot API não resolve @ de pessoa para id.
A ponte possível é o @ repetido nas duas redes, que é comum o bastante.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.services import telegram
from app.store import memory, telegram_members

logger = logging.getLogger(__name__)


def confirm_via_telegram(sender_id: str, instagram_username: str | None) -> bool:
    """Marca como pago quem usa o mesmo @ no Instagram e no grupo do Telegram.

    Exige igualdade exata do @ de propósito: um palpite errado silenciaria uma
    conversa de alguém que nunca comprou, o que é bem pior do que não achar.
    """
    settings = get_settings()
    if not settings.telegram_group_chat_id or not instagram_username:
        return False
    if memory.is_paid(sender_id):
        return False

    membro = telegram_members.find_by_username(instagram_username)
    if not membro or membro.get("status") not in telegram_members.DENTRO:
        return False

    # A tabela é o que vimos passar; o getChatMember é a situação de agora.
    if not telegram.is_in_group(membro["user_id"]):
        logger.info(
            "@%s consta na tabela mas já não está no grupo; não vou marcar como pago",
            instagram_username,
        )
        return False

    memory.mark_paid(sender_id)
    logger.info(
        "Compra confirmada pelo Telegram: IGSID=%s = @%s (user_id %s)",
        sender_id,
        instagram_username,
        membro["user_id"],
    )
    return True
