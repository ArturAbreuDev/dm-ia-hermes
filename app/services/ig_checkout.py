"""PIX na DM do Instagram pra quem não tem Telegram."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.config import get_settings
from app.services import instagram, straton
from app.store import memory, pedidos

logger = logging.getLogger(__name__)

REF_PREFIX = "hermes:ig:"


def parse_ref(valor: str | None) -> str | None:
    texto = (valor or "").strip()
    if not texto.startswith(REF_PREFIX):
        return None
    resto = texto[len(REF_PREFIX) :]
    igsid = resto.split(":", 1)[0].strip()
    return igsid or None


def pagina_url(slug: str) -> str:
    base = (get_settings().base_url or "https://dm-ia-hermes.vercel.app").rstrip("/")
    return f"{base}/pix/{slug}"


def dados_do_slug(slug: str) -> dict[str, Any]:
    meta = memory.get_lead(f"pixslug:{slug}")
    igsid = str(meta.get("igsid") or "")
    if not igsid:
        return {}
    lead = memory.get_lead(igsid)
    return {
        "codigo": str(lead.get("pix_ig_code") or ""),
        "qr": str(lead.get("pix_ig_qr") or ""),
        "pago": bool(lead.get("paid")),
        "preco": get_settings().active_price(),
    }


def enviar_pix(igsid: str, nome: str | None = None) -> str:
    """Gera (ou reusa) o PIX e devolve o texto com o link pra DM."""
    lead = memory.get_lead(igsid)
    codigo = str(lead.get("pix_ig_code") or "").strip()
    slug = str(lead.get("pix_ig_slug") or "").strip()
    hosted = str(lead.get("pix_ig_link") or "").strip()
    if not codigo:
        dados = _criar(igsid, nome or lead.get("name") or "amor")
        codigo = str(dados.get("pix_code") or dados.get("brcode") or "").strip()
        tx = str(dados.get("id") or dados.get("transaction_id") or "")
        qr = str(dados.get("qr_code") or dados.get("qr_code_url") or "")
        hosted = straton.pix_hosted_url(dados)
        slug = uuid.uuid4().hex[:12]
        lead = memory.get_lead(igsid)
        lead["pix_ig_code"] = codigo
        lead["pix_ig_tx"] = tx
        lead["pix_ig_qr"] = qr
        lead["pix_ig_slug"] = slug
        lead["pix_ig_link"] = hosted
        lead["entrega"] = "instagram"
        memory.save_lead(igsid, lead)
        memory.save_lead(f"pixslug:{slug}", {"igsid": igsid})
        pedidos.save(
            user_id=igsid,
            nome=nome or lead.get("name") or igsid,
            username=str(lead.get("username") or ""),
            origem="instagram",
            status="pending",
            amount=get_settings().active_price(),
            tx=tx,
            produto="Pack Instagram",
            pedido_id=f"tx:{tx}" if tx else f"ig:{igsid}",
        )
        if qr.startswith("http"):
            try:
                instagram.send_image_message(igsid, qr)
            except Exception:
                logger.exception("QR na DM falhou para %s", igsid)
        from app.services import alert

        cents = int(round(get_settings().active_price_amount() * 100))
        alert.notify_pix_status(
            "pix_pendente",
            nome or lead.get("name") or igsid,
            tx or slug,
            cents,
            detalhe=f"PIX na DM do Instagram · {igsid}",
        )
    elif not slug:
        slug = uuid.uuid4().hex[:12]
        lead["pix_ig_slug"] = slug
        memory.save_lead(igsid, lead)
        memory.save_lead(f"pixslug:{slug}", {"igsid": igsid})
    if not codigo:
        return "não rolou gerar o pix agora. tenta de novo em um minutinho."
    preco = get_settings().active_price()
    link = hosted if hosted.startswith("http") else pagina_url(slug)
    return (
        f"sem telegram? então é pix. R$ {preco}\n"
        f"{link}\n"
        "paga e me avisa. o pack eu mando nesse chat."
    )


def on_paid(igsid: str, detalhe: str = "") -> dict[str, Any]:
    """Marca pago, avisa na DM e tenta mandar o pack se tiver URL."""
    memory.mark_paid(igsid)
    memory.set_lead_flag(igsid, "entrega_instagram", True)
    tx = str(memory.get_lead(igsid).get("pix_ig_tx") or "")
    if tx:
        pedidos.mark_status(tx=tx, status="paid")
    pedidos.mark_status(user_id=igsid, status="paid")
    enviado = {"aviso": False, "pack": False}
    try:
        instagram.send_text_message(
            igsid, "pix caiu 🔥 já te mando o pack aqui no chat."
        )
        enviado["aviso"] = True
    except Exception:
        logger.exception("Aviso de pagamento na DM falhou para %s", igsid)
    url = (get_settings().pack_delivery_url or "").strip()
    if url.startswith("http"):
        tipo = "video" if any(url.lower().endswith(s) for s in (".mp4", ".mov")) else "image"
        try:
            if tipo == "video":
                instagram.send_video_message(igsid, url)
            else:
                instagram.send_image_message(igsid, url)
            enviado["pack"] = True
        except Exception:
            logger.exception("Pack automático falhou para %s", igsid)
    from app.services import alert

    extra = "pack enviado na DM" if enviado["pack"] else "MANDA O PACK NA DM DO INSTAGRAM"
    if detalhe:
        extra = f"{extra} · {detalhe}"
    alert.notify_confirmed(igsid, extra)
    return enviado


def _criar(igsid: str, nome: str) -> dict[str, Any]:
    settings = get_settings()
    chave = uuid.uuid4().hex
    return straton.create_cashin(
        amount=settings.active_price_amount(),
        external_id=f"{REF_PREFIX}{igsid}:{chave[:10]}",
        description="Priv da Lívia — pack no Instagram",
        customer_name=nome,
        idempotency_key=chave,
    )
