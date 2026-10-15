"""Grupo de prévias no Telegram — separado do chat pessoal e do VIP."""

from __future__ import annotations

import json
import logging
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import get_settings
from app.services import telegram
from app.store import runtime

logger = logging.getLogger(__name__)

CHAVE_ID = "telegram_previews_chat_id"
CHAVE_TITULO = "telegram_previews_title"
CHAVE_TRAVADO = "telegram_previews_locked"
CHAVE_CONVITE = "telegram_previews_invite"
CHAVE_POSTADAS = "telegram_previews_posted"
CHAVE_SEMANAL = "telegram_previews_weekly_at"
CHAVE_BOASVINDAS = "telegram_previews_welcome"

def _preco() -> str:
    return (get_settings().active_price() or "24,90").strip()


def checkout_url() -> str:
    """CTA no Telegram: abre o bot nosso (PIX), não o da Straton."""
    s = get_settings()
    bot = (s.telegram_vip_bot() or "liviagommes_bot").lstrip("@")
    return f"https://t.me/{bot}"


def descricao_canal() -> str:
    custom = str(runtime.get("telegram_previews_desc") or "").strip()
    if custom:
        return custom[:255]
    return (
        f"Prévia grátis. Completo sem corte no VIP. "
        f"R$ {_preco()} PIX anônimo — entra na hora. "
        f"Conteúdo novo toda semana. {checkout_url()}"
    )[:255]


class PreviewError(RuntimeError):
    pass


def _normalizar(texto: str) -> str:
    nfd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfd if not unicodedata.combining(c)).lower()


def titulo_de_previas(titulo: str | None) -> bool:
    t = _normalizar(titulo or "")
    return any(p in t for p in ("previa", "porevia", "preview"))


def ids_proibidos() -> set[str]:
    """Chat pessoal, alertas e VIP de quem pagou — nunca postar prévia aí."""
    s = get_settings()
    out: set[str] = set()
    for bruto in (
        s.telegram_default_chat_id,
        s.alert_chat_id,
        s.telegram_group_chat_id,
    ):
        valor = str(bruto or "").strip()
        if valor:
            out.add(valor)
    return out


def chat_id() -> str:
    s = get_settings()
    env = str(s.telegram_previews_chat_id or "").strip()
    banco = str(runtime.get(CHAVE_ID) or "").strip()
    cid = env or banco
    if not cid:
        return ""
    if cid in ids_proibidos():
        logger.error("prévias recusou destino pessoal/VIP")
        return ""
    return cid


def convite_publico() -> str:
    """Link permanente do grupo de prévias, se o bot for admin."""
    s = get_settings()
    fixo = str(s.telegram_previews_url or "").strip()
    if fixo:
        return fixo
    cid = chat_id()
    if not cid:
        return ""
    cached = str(runtime.get(CHAVE_CONVITE) or "").strip()
    if cached:
        return cached
    try:
        link = telegram.create_chat_invite_link(
            name="previas", member_limit=None, chat_id=cid
        )
    except Exception:
        logger.exception("convite das prévias falhou")
        return ""
    if link:
        runtime.set(CHAVE_CONVITE, link)
    return link or ""


def mesmo(outro: str | int | None) -> bool:
    cid = chat_id()
    if not cid or outro is None:
        return False
    return str(outro) == cid


def status() -> dict[str, str]:
    cid = chat_id()
    titulo = str(runtime.get(CHAVE_TITULO) or "").strip()
    if not cid:
        return {
            "ok": "",
            "titulo": "",
            "id": "",
            "texto": (
                "Grupo de prévias ainda não ligado. Manda qualquer mensagem "
                "no «livia porevias» com o bot admin — ele grava sozinho. "
                "Não usa o chat pessoal nem o grupo VIP."
            ),
        }
    nome = titulo or "prévias"
    return {
        "ok": "1",
        "titulo": nome,
        "id": cid,
        "texto": (
            f"Postagens do site caem só em «{nome}». "
            "Prévia nova toda semana. Chat pessoal e VIP ficam de fora."
        ),
    }


def lembrar(
    chat: dict | None, *, status_bot: str | None = None, forcar: bool = False
) -> bool:
    """Grava o id do grupo de prévias se o título bater e não for pessoal/VIP."""
    if not chat:
        return False
    tipo = chat.get("type")
    if tipo not in {"group", "supergroup", "channel"}:
        return False
    cid = str(chat.get("id") or "").strip()
    if not cid or cid in ids_proibidos():
        return False
    titulo = str(chat.get("title") or "")
    ja = chat_id()
    if ja and ja == cid:
        if titulo:
            runtime.set(CHAVE_TITULO, titulo[:120])
        if runtime.get(CHAVE_TRAVADO) != cid:
            try:
                travar_e_avisar(cid)
            except Exception:
                logger.exception("não deu pra travar o grupo de prévias")
        return False
    if ja:
        return False
    if not titulo_de_previas(titulo) and not forcar:
        return False
    if tipo == "channel":
        # Canal: getChatMember às vezes recusa mesmo com o bot admin.
        pass
    elif status_bot:
        if status_bot not in {"administrator", "creator"}:
            return False
    elif not bot_e_admin(cid):
        return False
    runtime.set(CHAVE_ID, cid)
    runtime.set(CHAVE_TITULO, titulo[:120] or "prévias")
    logger.info("Grupo de prévias ligado: %s", titulo)
    try:
        travar_e_avisar(cid)
    except Exception:
        logger.exception("não deu pra travar o grupo de prévias")
    return True


def bot_e_admin(cid: str) -> bool:
    """Só liga o grupo se o bot for admin — evita canal público alheio."""
    try:
        with httpx.Client(timeout=15) as client:
            eu = client.get(telegram._api_url("getMe")).json()
        if not eu.get("ok"):
            return False
        bid = (eu.get("result") or {}).get("id")
        membro = telegram.get_chat_member(bid, cid)
        if not membro:
            return False
        return membro.get("status") in {"administrator", "creator"}
    except Exception:
        logger.exception("não conferi se o bot é admin das prévias")
        return False


def chats_de_encaminhamento(mensagem: dict) -> list[dict]:
    achados: list[dict] = []
    direto = mensagem.get("forward_from_chat")
    if isinstance(direto, dict):
        achados.append(direto)
    origem = mensagem.get("forward_origin") or {}
    chat = origem.get("chat")
    if isinstance(chat, dict):
        achados.append(chat)
    return achados


def capturar_encaminhamento(mensagem: dict, *, dono: bool = False) -> bool:
    """No privado: encaminhou msg do grupo de prévias → liga e manda oi."""
    ligou = False
    for chat in chats_de_encaminhamento(mensagem):
        if lembrar(chat, forcar=dono):
            ligou = True
    if ligou or (chat_id() and chats_de_encaminhamento(mensagem)):
        try:
            mandar_oi()
        except Exception:
            logger.exception("falha ao mandar oi nas prévias")
        if ligou:
            try:
                publicar_do_funil(force=True)
            except Exception:
                logger.exception("dump das prévias no encaminhamento falhou")
        return True
    return ligou


def mandar_oi() -> str:
    dest = chat_id()
    if not dest:
        raise PreviewError("grupo de prévias ainda não está ligado")
    if dest in ids_proibidos():
        raise PreviewError("recusei postar em chat pessoal ou VIP")
    msg = telegram.send_text_message(dest, "oi", protect_content=True)
    mid = msg.get("message_id")
    return str(mid) if mid is not None else "ok"


def ids_candidatos(bruto: str) -> list[str]:
    """URL do Web K (#-100…) vira os chat_id que a Bot API aceita."""
    texto = str(bruto or "").strip()
    vistos: list[str] = []

    def add(valor: object) -> None:
        item = str(valor).strip()
        if item and item not in vistos:
            vistos.append(item)

    if not texto:
        return vistos
    add(texto)
    so_digitos = texto.lstrip("-")
    if not so_digitos.isdigit():
        return vistos
    n = int(so_digitos)
    add(f"-{n}")
    add(f"-100{n}")
    add(-(10**12 + n))
    if texto.startswith("-100") and len(so_digitos) > 3:
        resto = int(so_digitos[3:])
        add(f"-{resto}")
        add(f"-100{resto}")
        add(-(10**12 + resto))
    return vistos


def ligar_por_id(cid: str) -> dict[str, Any]:
    """Liga o canal/grupo pelo id (Telegram Web: #‑100…)."""
    return ligar_por_texto(cid)


def ligar_por_texto(bruto: str) -> dict[str, Any]:
    """Liga por @publico, t.me/nome ou id numérico."""
    texto = str(bruto or "").strip()
    if not texto:
        raise PreviewError("cola o @ do canal, o link t.me ou o id")
    if "t.me/" in texto.lower():
        parte = texto.split("t.me/", 1)[-1].split("?")[0].strip("/")
        if parte.startswith("+") or parte.lower().startswith("joinchat"):
            raise PreviewError(
                "link de convite (+) não serve. Coloca um @publico no canal "
                "ou encaminha um post do canal pro @liviagommes_bot"
            )
        texto = "@" + parte.lstrip("@")
    chat: dict[str, Any] | None = None
    usado = ""
    if texto.startswith("@"):
        chat = telegram.get_chat(texto)
        usado = str((chat or {}).get("id") or texto)
    else:
        for candidato in ids_candidatos(texto):
            chat = telegram.get_chat(candidato)
            if chat:
                usado = str(chat.get("id") or candidato)
                break
    if not chat:
        raise PreviewError(
            "não achei esse chat. No site: @publico do canal, ou encaminha "
            "um post do canal pro @liviagommes_bot"
        )
    if not lembrar(chat, status_bot="administrator", forcar=True):
        if not chat_id():
            raise PreviewError(
                "esse chat não parece de prévias (título) ou é o VIP/pessoal"
            )
        usado = chat_id()
    return {"id": usado, "titulo": chat.get("title") or ""}


def travar_e_avisar(cid: str) -> None:
    """Só admin posta; conteúdo protegido contra encaminhar fácil."""
    try:
        _set_permissions(cid)
    except Exception:
        logger.info("setChatPermissions falhou (canal não usa isso)")
    _set_description(cid)
    runtime.set(CHAVE_TRAVADO, cid)


def _set_permissions(cid: str) -> None:
    # Membros comuns não mandam nada — evita vazamento e spam.
    permissoes = {
        "can_send_messages": False,
        "can_send_audios": False,
        "can_send_documents": False,
        "can_send_photos": False,
        "can_send_videos": False,
        "can_send_video_notes": False,
        "can_send_voice_notes": False,
        "can_send_polls": False,
        "can_send_other_messages": False,
        "can_add_web_page_previews": False,
        "can_change_info": False,
        "can_invite_users": False,
        "can_pin_messages": False,
        "can_manage_topics": False,
    }
    with httpx.Client(timeout=20) as client:
        response = client.post(
            telegram._api_url("setChatPermissions"),
            json={"chat_id": cid, "permissions": permissoes},
        )
        telegram._raise_for_telegram(response)


def _set_description(cid: str) -> None:
    with httpx.Client(timeout=20) as client:
        response = client.post(
            telegram._api_url("setChatDescription"),
            json={"chat_id": cid, "description": descricao_canal()},
        )
        if not response.json().get("ok"):
            logger.info("setChatDescription: %s", response.json().get("description"))


def _markup_vip() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": f"Liberar VIP · R$ {_preco()} 🔥", "url": checkout_url()}]
        ]
    }


def _boas_vindas() -> str:
    ck = checkout_url()
    return (
        "Aqui é PRÉVIA. O que você quer de verdade tá no VIP.\n\n"
        f"R$ {_preco()} · PIX anônimo · cai no canal na hora\n"
        "Completo, sem corte, conteúdo novo toda semana.\n\n"
        f"Clica e entra:\n{ck}"
    )


def legenda(texto: str = "") -> str:
    ck = checkout_url()
    extra = (
        "Isso é só a PRÉVIA 🔥\n"
        "O sem corte tá no VIP.\n"
        f"R$ {_preco()} · PIX anônimo · entra na hora\n"
        "Conteúdo novo toda semana.\n\n"
        f"{ck}"
    )
    corpo = (texto or "").strip()
    if ck in corpo:
        return corpo[:1024]
    if len(corpo) > 160:
        corpo = ""
    full = f"{corpo}\n\n{extra}" if corpo else extra
    return full[:1024]


def painel_itens() -> list[dict[str, str]]:
    """Vídeos/fotos do funil com a legenda de conversão, pra tela /publicar."""
    from app.services import funnel

    itens: list[dict[str, str]] = []
    for item in funnel.midias_previa():
        url = str(item.get("video_url") or item.get("photo_url") or "").strip()
        eh_video = bool(item.get("video_url") or item.get("video_file_id")) or _parece_video(url)
        itens.append(
            {
                "id": str(item.get("id") or ""),
                "kind": "vídeo" if eh_video else "foto",
                "url": url,
                "caption": legenda(item.get("text") or ""),
            }
        )
    return itens


def publicar_um(item_id: str, caption: str = "") -> str:
    from app.services import funnel

    alvo = str(item_id or "").strip()
    for item in funnel.midias_previa():
        if str(item.get("id") or "") != alvo:
            continue
        extra = (caption or "").strip()
        if extra:
            item = {**item, "caption": extra, "text": extra}
        return publicar(item)
    raise PreviewError("não achei essa prévia no funil")


def aplicar_canal(*, descricao: str = "", pin: bool = True) -> None:
    dest = chat_id()
    if not dest:
        raise PreviewError("grupo de prévias ainda não está ligado")
    extra = (descricao or "").strip()
    if extra:
        runtime.set("telegram_previews_desc", extra[:255])
    travar_e_avisar(dest)
    if pin:
        runtime.set(CHAVE_BOASVINDAS, "")
        _garantir_boas_vindas(dest)


def publicar(item: dict[str, Any]) -> str:
    dest = chat_id()
    if not dest:
        raise PreviewError("grupo de prévias ainda não está ligado")
    if dest in ids_proibidos():
        raise PreviewError("recusei postar em chat pessoal ou VIP")
    caption = legenda(item.get("caption") or item.get("text") or "")
    url = (item.get("media_url") or item.get("video_url") or item.get("photo_url") or "").strip()
    video_id = str(item.get("video_file_id") or "").strip()
    photo_id = str(item.get("photo_file_id") or "").strip()
    extra = {"protect_content": True, "reply_markup": _markup_vip()}
    msg: dict[str, Any]
    if video_id:
        msg = telegram.send_video_url(dest, video_id, caption, **extra)
    elif url and _parece_video(url):
        msg = telegram.send_video_url(dest, url, caption, **extra)
    elif photo_id:
        msg = telegram.send_photo_url(dest, photo_id, caption, **extra)
    elif url:
        msg = telegram.send_photo_url(dest, url, caption, **extra)
    elif caption:
        msg = telegram.send_text_message(
            dest, caption[:4096], protect_content=True, reply_markup=_markup_vip()
        )
    else:
        raise PreviewError("manda um texto ou uma mídia")
    mid = msg.get("message_id")
    return str(mid) if mid is not None else "ok"


def _postadas() -> set[str]:
    bruto = runtime.get(CHAVE_POSTADAS) or "[]"
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError:
        return set()
    if not isinstance(dados, list):
        return set()
    return {str(x) for x in dados}


def _marcar_postada(chave: str) -> None:
    atual = _postadas()
    atual.add(chave)
    runtime.set(CHAVE_POSTADAS, json.dumps(sorted(atual)))


def _chave_item(item: dict[str, Any]) -> str:
    return (
        str(item.get("id") or "")
        + ":"
        + (
            str(item.get("video_file_id") or "")
            or str(item.get("photo_file_id") or "")
            or str(item.get("video_url") or "")
            or str(item.get("photo_url") or "")
            or str(item.get("media_url") or "")
        )
    )


def _garantir_boas_vindas(dest: str) -> None:
    if runtime.get(CHAVE_BOASVINDAS) == dest:
        return
    msg = telegram.send_text_message(
        dest,
        _boas_vindas(),
        protect_content=True,
        reply_markup=_markup_vip(),
    )
    mid = msg.get("message_id")
    if mid:
        try:
            telegram.pin_chat_message(dest, int(mid))
        except Exception:
            logger.info("não pinou o aviso das prévias")
    runtime.set(CHAVE_BOASVINDAS, dest)


def publicar_do_funil(*, force: bool = False) -> dict[str, Any]:
    """Manda todas as mídias do RMK/Start pro grupo, com link do checkout."""
    from app.services import funnel

    dest = chat_id()
    if not dest:
        raise PreviewError("grupo de prévias ainda não está ligado")
    try:
        travar_e_avisar(dest)
    except Exception:
        logger.exception("não atualizei a descrição do grupo")
    if force:
        runtime.set(CHAVE_BOASVINDAS, "")
    _garantir_boas_vindas(dest)
    ja = set() if force else _postadas()
    feitos: list[dict[str, Any]] = []
    for item in funnel.midias_previa():
        chave = _chave_item(item)
        if chave in ja:
            feitos.append({"id": item.get("id"), "ok": True, "via": "ja"})
            continue
        try:
            mid = publicar(item)
            _marcar_postada(chave)
            feitos.append({"id": item.get("id"), "ok": True, "via": mid})
            time.sleep(0.6)
        except Exception as erro:  # noqa: BLE001
            logger.exception("prévia %s falhou", item.get("id"))
            feitos.append({"id": item.get("id"), "ok": False, "erro": str(erro)[:180]})
    return {"grupo": dest, "enviados": feitos}


def publicar_semanal(*, force: bool = False) -> dict[str, Any]:
    """Uma prévia por semana (segunda 18h), rodando as mídias do RMK."""
    from app.services import funnel

    dest = chat_id()
    if not dest:
        return {"ok": False, "motivo": "grupo_nao_ligado"}
    agora = datetime.now(timezone.utc)
    ultimo = runtime.get(CHAVE_SEMANAL) or ""
    if ultimo and not force:
        try:
            quando = datetime.fromisoformat(ultimo.replace("Z", "+00:00"))
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=timezone.utc)
            if agora - quando < timedelta(days=6):
                return {"ok": True, "via": "cedo"}
        except ValueError:
            pass
    itens = funnel.midias_previa()
    if not itens:
        return {"ok": False, "motivo": "sem_midia"}
    ja = _postadas()
    escolhido = next((i for i in itens if _chave_item(i) not in ja), None)
    if escolhido is None:
        escolhido = itens[int(agora.timestamp() // 86400) % len(itens)]
    mid = publicar(escolhido)
    _marcar_postada(_chave_item(escolhido))
    runtime.set(CHAVE_SEMANAL, agora.isoformat())
    return {"ok": True, "id": escolhido.get("id"), "via": mid, "grupo": dest}


def _parece_video(url: str) -> bool:
    u = (url or "").lower().split("?", 1)[0]
    return u.endswith((".mp4", ".mov", ".m4v", ".webm"))
