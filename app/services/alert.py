"""Avisa a gente no celular quando a conversa fica séria.

A Lívia dá conta de responder sozinha, mas não de fechar: quem diz que vai
pagar, quem tentou pagar e viu erro e quem já pagou merecem um olho humano na
hora, e não no relatório do dia seguinte. O aviso sai pelo Telegram porque é o
único canal já montado aqui e chega como push no celular sem custo por mensagem.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.services import engagement, telegram
from app.store import memory

logger = logging.getLogger(__name__)

# Um aviso por motivo, por pessoa. Sem isso um "quanto custa" repetido viraria
# cinco notificações, e aviso demais é a mesma coisa que aviso nenhum: em dois
# dias ninguém olha mais. O campo fica no lead, que é o que sobrevive ao deploy.
_MOTIVOS: dict[str, tuple[str, str]] = {
    # Dinheiro confirmado pela plataforma tem campo próprio, separado de "pagou",
    # que é só a pessoa dizendo que pagou. Os dois avisam: um é a promessa, o
    # outro é o dinheiro, e quem só olha o primeiro nunca sabe se caiu.
    "confirmado": ("avisado_confirmado", "DINHEIRO CONFIRMADO"),
    "pagou": ("avisado_pagou", "DISSE QUE PAGOU"),
    "erro_pagamento": ("avisado_erro_pagamento", "TENTOU PAGAR E DEU ERRO"),
    "duvida_com_link": ("avisado_duvida_link", "ESTÁ NO CHECKOUT COM DÚVIDA"),
    "quer_comprar": ("avisado_quer_comprar", "QUER COMPRAR"),
    "sem_telegram": ("avisado_sem_telegram", "SEM TELEGRAM — PIX NA DM"),
    # PIX gerado no bot e ainda não pago. Sem aviso humano isso expira em ~30min.
    "pix_pendente": ("avisado_pix_pendente", "PIX ABERTO — VAI EXPIRAR"),
    "pix_expirou": ("avisado_pix_expirou", "PIX EXPIROU SEM PAGAR"),
}


def motivo(text: str, flags, paid: bool, lead: dict) -> str | None:
    """Por que essa mensagem merece um aviso, se merecer.

    A ordem é a prioridade, do mais perto do dinheiro para o mais longe. Quem
    tentou pagar e viu erro vem antes de quem só perguntou o preço porque ali o
    dinheiro já estava saindo e travou.
    """
    flags = flags or frozenset()
    if paid:
        return "pagou"
    if "erro_pagamento" in flags:
        return "erro_pagamento"
    if "sem_telegram" in flags:
        return "sem_telegram"
    if lead.get("link_sent") and flags & {"duvida_fluxo", "como_funciona"}:
        return "duvida_com_link"
    if engagement.wants_to_buy(text):
        return "quer_comprar"
    return None


def maybe_notify(
    sender_id: str,
    text: str,
    flags,
    paid: bool,
    lead: dict,
    perfil: dict | None = None,
    calada: bool = False,
) -> str | None:
    """Manda o aviso se for o caso. Nunca levanta erro para quem chamou.

    Um aviso que falha não pode derrubar a resposta dela: a venda é mais
    importante que a notificação, então aqui tudo que der errado só vira log.
    """
    razao = motivo(text, flags, paid, lead)
    if not razao:
        return None
    return razao if _enviar(sender_id, razao, text, lead, perfil, calada) else None


def _enviar(
    sender_id: str,
    razao: str,
    text: str,
    lead: dict,
    perfil: dict | None = None,
    calada: bool = False,
) -> bool:
    campo, titulo = _MOTIVOS[razao]
    if lead.get(campo):
        return False

    settings = get_settings()
    destino = settings.chat_dono_privado()
    if not settings.alerts_enabled or not settings.telegram_bot_token or not destino:
        logger.info(
            "Aviso %s de IGSID=%s não saiu: canal de aviso não configurado", razao, sender_id
        )
        return False

    try:
        telegram.send_text_message(destino, _texto(titulo, sender_id, text, lead, perfil, calada))
    except Exception:
        logger.exception("Falha ao avisar sobre IGSID=%s", sender_id)
        return False

    # Marca só depois de sair. Se o envio falhar, a próxima mensagem tenta de novo.
    memory.set_lead_flag(sender_id, campo, True)
    logger.info("Avisado: %s de IGSID=%s", razao, sender_id)
    return True


def notify_confirmed(sender_id: str, detalhe: str) -> bool:
    """Aviso do dinheiro que a plataforma confirmou.

    Não passa por `motivo` porque aqui não existe mensagem: quem contou foi o
    webhook do checkout, não a pessoa.
    """
    return _enviar(sender_id, "confirmado", detalhe, memory.get_lead(sender_id))


def notify_pix_status(
    razao: str,
    buyer_name: str,
    transaction_id: str,
    amount_cents: int | None = None,
    detalhe: str = "",
) -> bool:
    """Avisa que um PIX nasceu ou morreu na Straton — sem IGSID na maioria das vezes.

    O comprador está no Telegram do bot, não necessariamente no Instagram. O
    aviso serve pra você ir atrás dele no bot antes do expires_at.
    """
    if razao not in {"pix_pendente", "pix_expirou"}:
        return False
    settings = get_settings()
    destino = settings.chat_dono_privado()
    if not settings.alerts_enabled or not settings.telegram_bot_token or not destino:
        logger.info("Aviso %s não saiu: canal de aviso não configurado", razao)
        return False

    # Idempotência por transação, não por lead: cada PIX é um evento novo.
    chave = f"straton:{razao}:{transaction_id}"
    if memory.get_lead(chave).get("avisado"):
        return False

    _, titulo = _MOTIVOS[razao]
    valor = f"R$ {(amount_cents or 0) / 100:.2f}" if amount_cents else "?"
    linhas = [
        titulo,
        f"Comprador: {buyer_name or '(sem nome)'}",
        f"Valor: {valor}",
        f"TX: {transaction_id}",
    ]
    if detalhe:
        linhas.append(detalhe.strip()[:280])
    linhas.append("Ele está no bot do Telegram — cobra o PIX agora.")
    try:
        telegram.send_text_message(destino, "\n".join(linhas))
    except Exception:
        logger.exception("Falha ao avisar PIX %s", transaction_id)
        return False

    memory.save_lead(chave, {"avisado": True, "buyer_name": buyer_name})
    logger.info("Avisado %s tx=%s buyer=%s", razao, transaction_id, buyer_name)
    return True


def _texto(
    titulo: str,
    sender_id: str,
    text: str,
    lead: dict,
    perfil: dict | None,
    calada: bool,
) -> str:
    perfil = perfil or {}
    nome = (perfil.get("name") or "").strip()
    arroba = (perfil.get("username") or lead.get("username") or "").strip()
    quem = " ".join(p for p in [nome, f"(@{arroba})" if arroba else ""] if p)

    situacao = [f"{_n(lead, 'replies')} respostas"]
    if lead.get("link_sent"):
        situacao.append("link já enviado")
    if lead.get("muted"):
        situacao.append("silenciado")
    if calada:
        # A informação mais importante da mensagem: ninguém vai responder por nós.
        situacao.append("ELA NÃO VAI RESPONDER")

    linhas = [
        titulo,
        quem or f"IGSID {sender_id}",
        f'"{text.strip()[:280]}"',
        " · ".join(situacao),
    ]
    if arroba:
        linhas.append(f"https://instagram.com/{arroba}")
    return "\n".join(linhas)


def _n(lead: dict, campo: str) -> int:
    try:
        return int(lead.get(campo, 0))
    except (TypeError, ValueError):
        return 0
