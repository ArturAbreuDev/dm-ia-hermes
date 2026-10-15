"""Bot de vendas no Telegram: Start, PIX/cartão na hora e remarketing."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import ROOT_DIR, get_settings
from app.services import alert, funnel, straton, telegram
from app.store import pedidos, telegram_leads, telegram_members

logger = logging.getLogger(__name__)

BOT_NAME = "Priv da Lívia 💋"
SHORT_DESCRIPTION = (
    "Priv da Lívia — conteúdo quente que o Instagram não deixa. "
    "Start, paga no PIX ou cartão e cai no grupo."
)
DESCRIPTION = (
    "Seja muito bem-vindo! 😍🔥\n"
    "Falta bem pouco para você entrar no meu Canal VIP.\n\n"
    "🌶️ Interação com os assinantes\n"
    "🌶️ Fotos e vídeos exclusivos\n"
    "🔥 Conteúdo novo toda semana\n\n"
    "Toca em Start, escolhe o acesso e cai no grupo na hora."
)
COMMANDS = [
    {"command": "start", "description": "Entrar no priv"},
    {"command": "pix", "description": "Gerar PIX agora"},
    {"command": "parar", "description": "Parar os lembretes"},
]
COVER = ROOT_DIR / "assets" / "telegram" / "cover.jpg"
REF_PREFIX = "hermes:tg:"
_PERFIL_FLAG = "tg_profile_synced"
_PERFIL_HASH = "tg_profile_payload"
_IDIOMAS_PERFIL = ("", "en", "pt")


def _texto_chat_vazio() -> str:
    """Cartão do chat vazio (foto grande + texto + Start). Só o bloco 'Antes do Start'."""
    perfil = funnel.banner()
    texto = (perfil.get("text") or "").strip()
    if texto:
        return texto[:512]
    return DESCRIPTION[:512]


def perfil_desejado() -> dict[str, str]:
    perfil = funnel.banner()
    start = funnel.start_payload()
    foto = (perfil.get("photo_url") or "").strip()
    if not foto.startswith("http"):
        foto = (start.get("photo_url") or "").strip()
    return {
        "name": (perfil.get("name") or BOT_NAME).strip()[:64],
        "short": (perfil.get("short") or SHORT_DESCRIPTION).strip()[:120],
        "text": _texto_chat_vazio(),
        "photo_url": foto if foto.startswith("http") else "",
    }


def _tentar_perfil(nome: str, fn) -> str:
    try:
        fn()
        return "ok"
    except Exception as erro:
        msg = str(erro)
        logger.exception("Perfil %s falhou", nome)
        if "429" in msg or "Too Many" in msg:
            return "rate_limit"
        return "erro"


def _cache_perfil() -> dict[str, str]:
    from app.store import runtime
    import json

    bruto = runtime.get(_PERFIL_HASH)
    if not bruto:
        return {}
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError:
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar_cache_perfil(wanted: dict[str, str]) -> None:
    from app.store import runtime
    import json

    runtime.set(_PERFIL_HASH, json.dumps(wanted, ensure_ascii=False, sort_keys=True))
    runtime.set(_PERFIL_FLAG, "1")


def recorte_cartao(data: bytes) -> bytes:
    """Foto do cartão 'What can this bot do?': 640x360, exigência do BotFather."""
    from io import BytesIO

    from PIL import Image

    im = Image.open(BytesIO(data)).convert("RGB")
    w, h = im.size
    alvo = 16 / 9
    if w / max(h, 1) > alvo:
        nw = max(1, int(h * alvo))
        left = (w - nw) // 2
        im = im.crop((left, 0, left + nw, h))
    else:
        nh = max(1, int(w / alvo))
        top = (h - nh) // 2
        im = im.crop((0, top, w, top + nh))
    im = im.resize((640, 360), Image.Resampling.LANCZOS)
    out = BytesIO()
    im.save(out, format="JPEG", quality=90)
    return out.getvalue()


def _jpeg_perfil(data: bytes, mime: str) -> tuple[bytes, str]:
    if data[:3] == b"\xff\xd8\xff":
        return data, "image/jpeg"
    try:
        from io import BytesIO

        from PIL import Image

        im = Image.open(BytesIO(data))
        im = im.convert("RGB")
        im.thumbnail((640, 640))
        out = BytesIO()
        im.save(out, format="JPEG", quality=88)
        return out.getvalue(), "image/jpeg"
    except Exception:
        return data, (mime or "image/jpeg").split(";")[0]


def _aplicar_foto_perfil(foto_url: str) -> str:
    if foto_url.startswith("http"):
        def _foto_url() -> None:
            r = httpx.get(foto_url, timeout=15, follow_redirects=True)
            r.raise_for_status()
            mime = (r.headers.get("content-type") or "image/jpeg").split(";")[0]
            jpeg, mime = _jpeg_perfil(r.content, mime)
            telegram.set_my_profile_photo_bytes(jpeg, "banner.jpg", mime)

        return _tentar_perfil("foto_url", _foto_url)
    capa = COVER if COVER.exists() else ROOT_DIR / "app" / "static" / "telegram" / "cover.jpg"
    if capa.exists():
        return _tentar_perfil("foto_cover", lambda: telegram.set_my_profile_photo(capa))
    return "ausente"


def sync_profile(*, force: bool = False) -> dict[str, Any]:
    """Nome, textos e foto que aparecem no Telegram ANTES do Start."""
    wanted = perfil_desejado()
    anterior = _cache_perfil()
    if not force and anterior == wanted:
        return {
            "skipped": True,
            "name": "igual",
            "short": "igual",
            "description": "igual",
            "foto": "igual",
        }
    feito: dict[str, Any] = {"skipped": False}
    if force or anterior.get("name") != wanted["name"]:
        feito["name"] = _tentar_perfil(
            "name", lambda: telegram.set_my_name(wanted["name"])
        )
    else:
        feito["name"] = "igual"
    if force or anterior.get("short") != wanted["short"]:
        for lang in _IDIOMAS_PERFIL:
            chave = "short" if not lang else f"short_{lang}"
            feito[chave] = _tentar_perfil(
                chave,
                lambda lang=lang: telegram.set_my_short_description(
                    wanted["short"], language_code=lang
                ),
            )
    else:
        feito["short"] = "igual"
    if force or anterior.get("text") != wanted["text"]:
        for lang in _IDIOMAS_PERFIL:
            chave = "description" if not lang else f"description_{lang}"
            feito[chave] = _tentar_perfil(
                chave,
                lambda lang=lang: telegram.set_my_description(
                    wanted["text"], language_code=lang
                ),
            )
    else:
        feito["description"] = "igual"
    feito["commands"] = _tentar_perfil(
        "commands", lambda: telegram.set_my_commands(COMMANDS)
    )
    if force or anterior.get("photo_url") != wanted["photo_url"]:
        feito["foto"] = _aplicar_foto_perfil(wanted["photo_url"])
    else:
        feito["foto"] = "igual"
    if "erro" not in feito.values() and "rate_limit" not in feito.values():
        _gravar_cache_perfil(wanted)
    return feito


def parse_ref(valor: str | None) -> str | None:
    texto = (valor or "").strip()
    if not texto.startswith(REF_PREFIX):
        return None
    resto = texto[len(REF_PREFIX) :]
    user_id = resto.split(":", 1)[0].strip()
    return user_id or None


def _preco() -> str:
    return get_settings().price_straton or get_settings().active_price()


def _botoes_venda() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": f"Acesso VIP — R$ {_preco()}", "callback_data": "pay_pix"}],
        ]
    }


def _texto_start(_nome: str | None) -> str:
    custom = funnel.start_text()
    if custom:
        return custom.replace("{preco}", _preco())
    return (
        "Seja muito bem-vindo! 😍🔥\n\n"
        f"Por apenas R$ {_preco()}, você pode entrar e passar um tempinho comigo."
    )


def _texto_rmk(step: int, _nome: str | None) -> str:
    passos = funnel.rmk_steps()
    if passos:
        idx = min(max(0, step), len(passos) - 1)
        if passos[idx].get("text"):
            return str(passos[idx]["text"]).replace("{preco}", _preco())
    if step == 0:
        return "O pix ainda tá aberto 👀 finaliza agora que você cai no Canal VIP na hora."
    if step == 1:
        return f"Ainda tô com sua vaga. É R$ {_preco()}. PIX ou cartão, você escolhe."
    return "Ainda dá tempo de entrar. O botão ainda libera o acesso."


def _baixar_midia(
    url: str, limite: int = 18 * 1024 * 1024, timeout: float = 12
) -> bytes | None:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            if len(r.content) > limite:
                return None
            return r.content
    except Exception:
        logger.exception("Download da mídia falhou")
        return None


def _chat_arquivo() -> str:
    return get_settings().chat_dono_privado()


def eh_dono(user_id: str | int | None) -> bool:
    dono = get_settings().chat_dono_privado()
    return bool(dono) and str(user_id or "") == dono


def file_id_de_mensagem(msg: dict[str, Any] | None, kind: str) -> str:
    if not isinstance(msg, dict):
        return ""
    if kind == "video":
        bloco = msg.get("video") or msg.get("animation") or msg.get("document") or {}
        return str(bloco.get("file_id") or "")
    fotos = msg.get("photo") or []
    if isinstance(fotos, list) and fotos:
        return str((fotos[-1] or {}).get("file_id") or "")
    return str((msg.get("document") or {}).get("file_id") or "")


def _apagar_msg(chat_id: str, msg: dict[str, Any] | None) -> None:
    if not isinstance(msg, dict) or not msg.get("message_id"):
        return
    try:
        telegram.delete_message(chat_id, int(msg["message_id"]))
    except Exception:
        logger.info("Não deu pra apagar a mídia de cache")


def cachear_na_telegram(url: str, kind: str) -> str:
    """Sobe a mídia uma vez no Telegram e devolve file_id (vale pra todo /start)."""
    dest = _chat_arquivo()
    if not dest or not (url or "").startswith("http"):
        return ""
    msg: dict[str, Any] | None = None
    try:
        if kind == "video":
            try:
                msg = telegram.send_video_url(dest, url)
            except Exception:
                logger.exception("Telegram não puxou a URL do vídeo, subindo arquivo")
                bruto = _baixar_midia(url, limite=49 * 1024 * 1024)
                if bruto:
                    msg = telegram.send_video_bytes(dest, bruto, filename="video.mp4")
        else:
            try:
                msg = telegram.send_photo_url(dest, url)
            except Exception:
                logger.exception("Telegram não puxou a URL da foto, subindo arquivo")
                bruto = _baixar_midia(url, limite=9 * 1024 * 1024)
                if bruto:
                    msg = telegram.send_photo_bytes(dest, bruto)
    except Exception:
        logger.exception("Cache da mídia no Telegram falhou")
        return ""
    fid = file_id_de_mensagem(msg, kind)
    _apagar_msg(dest, msg)
    return fid


def preparar_midias() -> dict[str, Any]:
    dados = funnel.load()
    cacheados = 0
    for node in dados.get("nodes") or []:
        data = node.get("data") or {}
        nid = str(node.get("id") or "")
        pares = (
            ("video_url", "video_file_id", "video"),
            ("photo_url", "photo_file_id", "photo"),
        )
        for url_k, id_k, kind in pares:
            url = str(data.get(url_k) or "").strip()
            ja = str(data.get(id_k) or "").strip()
            if url.startswith("http") and not ja:
                fid = cachear_na_telegram(url, kind)
                if fid:
                    funnel.anexar_midia(nid, id_k, fid)
                    cacheados += 1
    return {"ok": True, "cacheados": cacheados}


def _urls_video(node_id: str, blob_url: str) -> list[str]:
    saidas: list[str] = []
    if blob_url.startswith("http"):
        saidas.append(blob_url)
    base = (get_settings().base_url or "").rstrip("/")
    if base and node_id:
        proxy = f"{base}/media/funil/{node_id}/video_url"
        if proxy not in saidas:
            saidas.append(proxy)
    return saidas


def _enviar_conteudo(
    user_id: str,
    texto: str,
    markup: dict[str, Any],
    *,
    video_url: str = "",
    photo_url: str = "",
    video_file_id: str = "",
    photo_file_id: str = "",
    node_id: str = "",
    usar_cover: bool = False,
    caption_on_media: bool = True,
) -> None:
    texto = (texto or "").strip() or "Seja muito bem-vindo! Toca em Acesso VIP pra entrar."
    cap, resto = (texto[:1024], texto[1024:]) if caption_on_media else (None, "")
    tem_video = bool(video_file_id or (video_url or "").startswith("http"))

    def _texto() -> None:
        telegram.send_text_message(user_id, texto[:4096], reply_markup=markup)

    def _resto() -> None:
        if resto:
            telegram.send_text_message(user_id, resto[:4096], reply_markup=markup)

    def _guardar(campo: str, valor: str) -> None:
        if node_id and valor:
            try:
                funnel.anexar_midia(node_id, campo, valor)
            except Exception:
                logger.exception("Não gravou file_id da mídia")

    foto_ok = False
    markup_foto = None if (not caption_on_media or resto) else markup
    if photo_file_id:
        try:
            telegram.send_photo_url(
                user_id, photo_file_id, caption=cap, reply_markup=markup_foto
            )
            foto_ok = True
        except Exception:
            logger.exception("sendPhoto por file_id falhou")
    if not foto_ok and (photo_url or "").startswith("http"):
        try:
            msg = telegram.send_photo_url(
                user_id, photo_url, caption=cap, reply_markup=markup_foto
            )
            _guardar("photo_file_id", file_id_de_mensagem(msg, "photo"))
            foto_ok = True
        except Exception:
            logger.exception("sendPhoto por URL falhou")
            bruto = _baixar_midia(photo_url)
            if bruto:
                try:
                    msg = telegram.send_photo_bytes(
                        user_id, bruto, caption=cap, reply_markup=markup_foto
                    )
                    _guardar("photo_file_id", file_id_de_mensagem(msg, "photo"))
                    foto_ok = True
                except Exception:
                    logger.exception("sendPhoto por arquivo falhou")
    if not foto_ok and usar_cover and not tem_video:
        try:
            if COVER.exists():
                telegram.send_photo_bytes(
                    user_id,
                    COVER.read_bytes(),
                    filename=getattr(COVER, "name", "cover.jpg"),
                    caption=cap,
                    reply_markup=markup_foto,
                )
                foto_ok = True
        except Exception:
            logger.exception("sendPhoto da capa falhou")

    cap_video = None if foto_ok or not caption_on_media else cap
    markup_video = None if foto_ok or resto or not caption_on_media else markup
    video_ok = False
    if video_file_id:
        try:
            telegram.send_video_url(
                user_id, video_file_id, caption=cap_video, reply_markup=markup_video
            )
            video_ok = True
        except Exception:
            logger.exception("sendVideo por file_id falhou")
    if not video_ok and (video_url or "").startswith("http"):
        for alvo in _urls_video(node_id, video_url):
            try:
                msg = telegram.send_video_url(
                    user_id, alvo, caption=cap_video, reply_markup=markup_video
                )
                _guardar("video_file_id", file_id_de_mensagem(msg, "video"))
                video_ok = True
                break
            except Exception:
                logger.exception("sendVideo por URL falhou")
        if not video_ok:
            bruto = _baixar_midia(video_url, limite=16 * 1024 * 1024)
            if bruto:
                try:
                    msg = telegram.send_video_bytes(
                        user_id, bruto, caption=cap_video, reply_markup=markup_video
                    )
                    _guardar("video_file_id", file_id_de_mensagem(msg, "video"))
                    video_ok = True
                except Exception:
                    logger.exception("sendVideo por arquivo falhou")

    if foto_ok or video_ok:
        if caption_on_media:
            _resto()
        return
    if caption_on_media:
        _texto()


def _tentar_video(user_id: str, file_id: str, url: str) -> bool:
    if file_id:
        try:
            telegram.send_video_url(user_id, file_id, timeout=4)
            return True
        except Exception:
            logger.exception("sendVideo file_id falhou")
    return False


def _capa() -> Path | None:
    try:
        if COVER.exists():
            return COVER
    except Exception:
        return None
    alt = ROOT_DIR / "app" / "static" / "telegram" / "cover.jpg"
    if COVER == ROOT_DIR / "assets" / "telegram" / "cover.jpg" and alt.exists():
        return alt
    return None


def _tentar_foto(
    user_id: str,
    file_id: str,
    url: str,
    *,
    usar_cover: bool,
    caption: str | None = None,
    reply_markup: dict[str, Any] | None = None,
) -> bool:
    cap = (caption or "")[:1024] or None
    if file_id:
        try:
            telegram.send_photo_url(
                user_id, file_id, caption=cap, reply_markup=reply_markup, timeout=4
            )
            return True
        except Exception:
            logger.exception("sendPhoto file_id falhou")
    if (url or "").startswith("http"):
        try:
            telegram.send_photo_url(
                user_id, url, caption=cap, reply_markup=reply_markup, timeout=8
            )
            return True
        except Exception:
            logger.exception("sendPhoto URL falhou")
        bruto = _baixar_midia(url, limite=4 * 1024 * 1024, timeout=8)
        if bruto:
            try:
                telegram.send_photo_bytes(
                    user_id, bruto, caption=cap, reply_markup=reply_markup
                )
                return True
            except Exception:
                logger.exception("sendPhoto bytes falhou")
    capa = _capa() if usar_cover else None
    if capa is not None:
        try:
            telegram.send_photo_bytes(
                user_id,
                capa.read_bytes(),
                filename=capa.name,
                caption=cap,
                reply_markup=reply_markup,
            )
            return True
        except Exception:
            logger.exception("sendPhoto da capa falhou")
    return False


def _comando(texto: str) -> str:
    bruto = (texto or "").strip()
    if not bruto.startswith("/"):
        return bruto.lower()
    primeiro = bruto.split()[0]
    return primeiro.split("@", 1)[0].lower()


def identidade(from_user: dict | None) -> dict[str, str]:
    """Nome completo + @, no mesmo formato da lista da Straton."""
    u = from_user or {}
    first = str(u.get("first_name") or "").strip()
    last = str(u.get("last_name") or "").strip()
    username = str(u.get("username") or "").strip().lstrip("@")
    user_id = str(u.get("id") or "").strip()
    nome = " ".join(p for p in (first, last) if p)
    if not nome:
        nome = username or user_id or "Cliente"
    rotulo = nome
    if username:
        rotulo = f"{nome} @{username}"
    elif user_id:
        rotulo = f"{nome} {user_id}"
    return {
        "nome": nome[:80],
        "username": username[:64],
        "user_id": user_id,
        "rotulo": rotulo[:80],
    }


def handle_private_message(message: dict) -> str:
    from_user = message.get("from") or {}
    if from_user.get("is_bot"):
        return "bot"
    user_id = str(from_user.get("id") or "")
    if not user_id:
        return "sem_id"
    if eh_dono(user_id):
        return "dono"
    chat = message.get("chat") or {}
    tipo = chat.get("type") or ""
    chat_id = int(chat.get("id") or 0)
    if tipo not in {"", "private"} and chat_id < 0:
        return "ignorado"
    if tipo and tipo != "private":
        return "ignorado"
    texto = (message.get("text") or message.get("caption") or "").strip()
    cmd = _comando(texto)
    quem = identidade(from_user)

    if cmd in {"/parar", "parar", "/stop"}:
        telegram_leads.mark(user_id, status="stopped")
        pedidos.mark_status(user_id=user_id, status="stopped")
        telegram.send_text_message(
            user_id, "tudo bem, paro por aqui. se quiser voltar, é /start."
        )
        return "parou"
    if cmd in {"/pix", "pix"}:
        return _gerar_pix(user_id, quem)
    try:
        return _enviar_start(
            user_id, username=quem["username"] or None, first_name=quem["nome"]
        )
    except Exception:
        logger.exception("Start falhou, mandando texto simples")
        try:
            telegram.send_text_message(
                user_id, _texto_start(quem["nome"]), reply_markup=_botoes_venda()
            )
            return "start_texto"
        except Exception:
            logger.exception("Nem o texto do Start saiu")
            return "erro"


def handle_callback(query: dict) -> str:
    data = query.get("data") or ""
    from_user = query.get("from") or {}
    user_id = str(from_user.get("id") or "")
    callback_id = str(query.get("id") or "")
    if callback_id:
        try:
            telegram.answer_callback(callback_id)
        except Exception:
            logger.exception("answerCallbackQuery falhou")
    if not user_id:
        return "sem_id"
    if eh_dono(user_id):
        return "dono"
    if data in {"rmk_parar"}:
        telegram_leads.mark(user_id, status="stopped")
        telegram.send_text_message(user_id, "ok, sem mais lembretes.")
        return "parou"
    if data in {"pay_pix"}:
        return _gerar_pix(user_id, identidade(from_user))
    if data in {"start", "/start", "inicio"}:
        quem = identidade(from_user)
        return _enviar_start(
            user_id, username=quem["username"] or None, first_name=quem["nome"]
        )
    return "ignorado"


def on_joined_group(user_id: str) -> None:
    telegram_leads.mark_paid(str(user_id))
    pedidos.mark_status(user_id=str(user_id), status="paid")


def fulfill(user_id: str) -> str:
    """Pagamento confirmado: marca pago e manda o convite do grupo."""
    telegram_leads.mark_paid(user_id)
    pedidos.mark_status(user_id=str(user_id), status="paid")
    try:
        convite = telegram.create_chat_invite_link(name=f"vip-{user_id[:12]}")
    except Exception:
        logger.exception("Convite do grupo falhou para %s", user_id)
        convite = None
    if convite:
        telegram.send_text_message(
            user_id,
            f"pago 🔥 entra aqui, o link é só seu:\n{convite}",
        )
        return "liberado"
    telegram.send_text_message(
        user_id,
        "pago 🔥 já já te coloco no grupo. se demorar, me chama no instagram.",
    )
    return "pago_sem_grupo"


def nudge_open_pix(user_id: str, status: str) -> str:
    if eh_dono(user_id):
        return "dono"
    if status == "expired":
        texto = (
            "amor, aquele pix caiu. toca em PIX de novo que eu gero outro na hora."
        )
    else:
        texto = "amor, o pix ainda tá aberto. cola o código no banco e finaliza 🔥"
    try:
        telegram.send_text_message(user_id, texto, reply_markup=_botoes_venda())
    except Exception as erro:
        if _eh_bloqueio(erro):
            telegram_leads.mark(user_id, status="blocked")
            return "bloqueado"
        logger.exception("Nudge PIX no bot falhou para %s", user_id)
        return "erro"
    return "ok"


def _enviar_start(user_id: str, *, username: str | None, first_name: str | None) -> str:
    gaps = funnel.rmk_gaps_hours()
    proximo = datetime.now(timezone.utc) + timedelta(hours=gaps[0])
    lead = telegram_leads.upsert_start(
        user_id,
        username=username,
        first_name=first_name,
        next_rmk_at=proximo,
    )
    pedidos.save(
        user_id=user_id,
        nome=first_name or user_id,
        username=username or "",
        status="start" if lead.get("status") != "paid" else "paid",
        produto="Acesso VIP",
        amount=get_settings().active_price(),
        pedido_id=f"u:{user_id}",
    )
    if lead.get("status") == "paid":
        telegram.send_text_message(
            user_id, "você já está dentro 😏 se o link do grupo sumiu, me chama."
        )
        return "ja_pago"
    caption = _texto_start(first_name)
    markup = _botoes_venda()
    midia = funnel.start_payload()
    _enviar_conteudo(
        user_id,
        caption,
        markup,
        video_url=str(midia.get("video_url") or ""),
        photo_url="",
        video_file_id=str(midia.get("video_file_id") or ""),
        photo_file_id="",
        node_id=str(midia.get("id") or ""),
        usar_cover=False,
        caption_on_media=False,
    )
    telegram.send_text_message(user_id, caption[:4096], reply_markup=markup)
    return "start"


def _gerar_pix(user_id: str, ident: dict[str, str] | str) -> str:
    if isinstance(ident, str):
        ident = {
            "nome": ident,
            "rotulo": ident,
            "username": "",
            "user_id": user_id,
        }
    settings = get_settings()
    chave = uuid.uuid4().hex
    external = f"{REF_PREFIX}{user_id}:{chave[:10]}"
    try:
        dados = straton.create_cashin(
            amount=settings.active_price_amount(),
            external_id=external,
            description="Acesso VIP",
            customer_name=ident.get("rotulo") or ident.get("nome") or "Cliente",
            idempotency_key=chave,
        )
    except Exception:
        logger.exception("Gerar PIX falhou para %s", user_id)
        telegram.send_text_message(
            user_id,
            "não rolou gerar o pix agora. tenta de novo em um minutinho.",
        )
        return "pix_falhou"
    tx = str(dados.get("id") or dados.get("transaction_id") or "")
    preco = settings.active_price()
    pedidos.save(
        user_id=user_id,
        nome=ident.get("nome") or user_id,
        username=ident.get("username") or "",
        status="pending",
        amount=preco,
        tx=tx,
        produto="Acesso VIP",
        pedido_id=f"tx:{tx}" if tx else f"u:{user_id}",
    )
    pedidos.save(
        user_id=user_id,
        nome=ident.get("nome") or user_id,
        username=ident.get("username") or "",
        status="pending",
        amount=preco,
        tx=tx,
        produto="Acesso VIP",
        pedido_id=f"u:{user_id}",
    )
    codigo = str(dados.get("pix_code") or dados.get("brcode") or "")
    qr = str(dados.get("qr_code") or dados.get("qr_code_url") or "")
    caption = (
        f"PIX de R$ {_preco()} gerado 🔥\n"
        "paga e eu te mando o grupo na hora.\n\n"
        + (codigo or "o código tá no QR.")
    )
    markup = _botoes_venda()
    if qr.startswith("http"):
        try:
            telegram.send_photo_url(user_id, qr, caption=caption[:1024], reply_markup=markup)
        except Exception:
            logger.exception("QR do PIX não foi")
            telegram.send_text_message(user_id, caption[:4096], reply_markup=markup)
    else:
        telegram.send_text_message(user_id, caption[:4096], reply_markup=markup)
    cents = int(round(settings.active_price_amount() * 100))
    alert.notify_pix_status(
        "pix_pendente",
        ident.get("rotulo") or ident.get("nome") or user_id,
        tx or chave[:12],
        cents,
        detalhe=f"no nosso bot · Telegram {user_id}",
    )
    return "pix"


def process_due(limit: int = 8) -> dict[str, Any]:
    passos = funnel.rmk_steps()
    if passos and passos[-1].get("loop") is not False:
        minutos = int(passos[-1].get("loop_minutes") or 1440)
        telegram_leads.reativar_exaustos(
            min_step=len(passos),
            next_rmk_at=datetime.now(timezone.utc) + timedelta(minutes=max(5, minutos)),
        )
    itens = telegram_leads.due(limit=limit)
    feitos: list[dict] = []
    for item in itens:
        resultado = _enviar_rmk(item)
        feitos.append({"user_id": item["user_id"], "ok": resultado == "ok", "via": resultado})
    return {"due": len(itens), "resultados": feitos}


def _enviar_rmk(item: dict[str, Any]) -> str:
    user_id = item["user_id"]
    if eh_dono(user_id):
        telegram_leads.mark(user_id, status="stopped")
        return "dono"
    membro = telegram_members.find_by_username(item.get("username") or "")
    if membro and membro.get("status") in telegram_members.DENTRO:
        telegram_leads.mark_paid(user_id)
        return "ja_no_grupo"
    step = int(item.get("rmk_step") or 0)
    passos = funnel.rmk_steps()
    idx = min(max(0, step), max(0, len(passos) - 1)) if passos else 0
    texto = _texto_rmk(idx, item.get("first_name"))
    video = ""
    foto = ""
    video_id = ""
    foto_id = ""
    nid = ""
    if passos:
        video = str(passos[idx].get("video_url") or "")
        foto = str(passos[idx].get("photo_url") or "")
        video_id = str(passos[idx].get("video_file_id") or "")
        foto_id = str(passos[idx].get("photo_file_id") or "")
        nid = str(passos[idx].get("id") or "")
    try:
        _enviar_conteudo(
            user_id,
            texto,
            _botoes_venda(),
            video_url=video,
            photo_url=foto,
            video_file_id=video_id,
            photo_file_id=foto_id,
            node_id=nid,
        )
    except Exception as erro:
        if _eh_bloqueio(erro):
            telegram_leads.mark(user_id, status="blocked")
            return "bloqueado"
        logger.exception("RMK Telegram falhou para %s", user_id)
        return "erro"
    agora = datetime.now(timezone.utc)
    if not passos:
        telegram_leads.mark(
            user_id, rmk_step=0, next_rmk_at=agora + timedelta(hours=24)
        )
        return "ok"
    ultimo = len(passos) - 1
    if idx < ultimo:
        nxt = idx + 1
        minutos = int(passos[nxt].get("minutes") or 180)
        telegram_leads.mark(
            user_id,
            rmk_step=nxt,
            next_rmk_at=agora + timedelta(minutes=max(1, minutos)),
        )
        return "ok"
    if passos[ultimo].get("loop") is False:
        telegram_leads.mark(user_id, status="stopped", rmk_step=ultimo)
        return "ok"
    minutos = int(passos[ultimo].get("loop_minutes") or 1440)
    telegram_leads.mark(
        user_id,
        rmk_step=ultimo,
        next_rmk_at=agora + timedelta(minutes=max(5, minutos)),
    )
    return "ok"


def _eh_bloqueio(erro: Exception) -> bool:
    msg = str(erro).lower()
    return any(
        trecho in msg
        for trecho in (
            "blocked",
            "deactivated",
            "chat not found",
            "bot was kicked",
            "user is deactivated",
            "forbidden",
        )
    )
