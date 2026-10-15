"""Painel pra programar feed, reels e stories."""

from __future__ import annotations

import html
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import get_settings
from app.services import previews, scheduler
from app.store import schedule, uploads

router = APIRouter(include_in_schema=False)

FUSO = ZoneInfo("America/Sao_Paulo")

_AVISOS = {
    "agendado": ("ok", "Agendado. Na hora marcada ele sobe sozinho."),
    "publicado": ("ok", "Publicado agora."),
    "grupo-nao-ligado": (
        "erro",
        "O grupo de prévias ainda não está ligado. Manda um oi no "
        "«livia porevias» com o bot como admin e tenta de novo.",
    ),
    "cancelado": ("ok", "Cancelado."),
    "arquivo-grande": (
        "erro",
        "Arquivo maior que 4 MB (limite free do upload). "
        "Pra reel grande, cole a URL do vídeo no campo de link.",
    ),
    "sem-midia": ("erro", "Manda um arquivo ou cola uma URL."),
    "horario-invalido": ("erro", "Horário inválido."),
    "falha": ("erro", "Não deu pra publicar. Confira o erro na lista."),
    "rmk-ok": ("ok", "Prévias do remarketing foram pro grupo, com o link do VIP."),
    "rmk-falha": (
        "erro",
        "Não deu pra postar no canal. Liga o canal abaixo (@publico ou "
        "encaminha um post pro @liviagommes_bot) e tenta de novo.",
    ),
    "ligado": ("ok", "Canal de prévias ligado. Agora publica pelo site."),
    "ligar-falha": ("erro", "Não liguei o canal."),
    "desc-ok": ("ok", "Descrição e pin de boas-vindas foram pro canal."),
    "item-ok": ("ok", "Prévia publicada no canal, com CTA."),
    "item-falha": ("erro", "Não deu pra publicar essa prévia."),
    "sem-funil": ("erro", "Não tem vídeo/foto no funil ainda. Sobe no /fluxo."),
}


def _check(senha: str) -> None:
    configurada = get_settings().diary_password
    if not configurada:
        raise HTTPException(status_code=503, detail="Defina DIARY_PASSWORD")
    if senha != configurada:
        raise HTTPException(status_code=403, detail="Senha incorreta")


@router.get("/publicar", response_class=HTMLResponse)
def pagina(k: str = "", aviso: str = "", msg: str = "") -> HTMLResponse:
    if not k:
        return HTMLResponse(_login())
    _check(k)
    # Sempre tenta publicar o que já venceu — funciona mesmo sem cron pago.
    try:
        scheduler.process_due()
    except Exception:
        pass
    return HTMLResponse(_page(k, aviso, msg))


@router.post("/publicar")
async def agendar(
    k: str = Form(...),
    kind: str = Form(...),
    caption: str = Form(""),
    quando: str = Form(...),
    agora: str = Form(""),
    media_url: str = Form(""),
    arquivo: UploadFile | None = File(None),
) -> RedirectResponse:
    _check(k)
    kind = (kind or "").strip().lower()
    if kind not in schedule.KINDS:
        return RedirectResponse(url=f"/publicar?k={k}&aviso=falha", status_code=303)

    url = (media_url or "").strip()
    if arquivo and arquivo.filename:
        dados = await arquivo.read()
        try:
            salvo = uploads.save(
                dados,
                arquivo.content_type or "application/octet-stream",
                arquivo.filename,
            )
            url = salvo["url"]
        except ValueError:
            return RedirectResponse(
                url=f"/publicar?k={k}&aviso=arquivo-grande", status_code=303
            )
    if kind == "previas" and not previews.chat_id():
        return RedirectResponse(
            url=f"/publicar?k={k}&aviso=grupo-nao-ligado", status_code=303
        )
    if not url and not (kind == "previas" and (caption or "").strip()):
        return RedirectResponse(url=f"/publicar?k={k}&aviso=sem-midia", status_code=303)

    if agora == "1":
        scheduled_for = datetime.now(FUSO)
    else:
        try:
            # datetime-local: 2026-09-24T22:30
            scheduled_for = datetime.strptime(quando, "%Y-%m-%dT%H:%M").replace(
                tzinfo=FUSO
            )
        except ValueError:
            return RedirectResponse(
                url=f"/publicar?k={k}&aviso=horario-invalido", status_code=303
            )

    schedule.create(
        kind=kind,
        media_url=url,
        caption=caption.strip(),
        share_to_feed=True,
        scheduled_for=scheduled_for.astimezone(ZoneInfo("UTC")),
    )

    if agora == "1" or scheduled_for <= datetime.now(FUSO):
        out = scheduler.process_due()
        ok = any(r.get("ok") for r in out.get("resultados") or [])
        aviso = "publicado" if ok else "agendado"
        if out.get("resultados") and not ok:
            aviso = "falha"
        return RedirectResponse(url=f"/publicar?k={k}&aviso={aviso}", status_code=303)

    return RedirectResponse(url=f"/publicar?k={k}&aviso=agendado", status_code=303)


@router.post("/publicar/cancelar")
def cancelar(k: str = Form(...), id: str = Form(...)) -> RedirectResponse:
    _check(k)
    schedule.cancel(id)
    return RedirectResponse(url=f"/publicar?k={k}&aviso=cancelado", status_code=303)


@router.post("/publicar/rodar")
def rodar(k: str = Form(...)) -> RedirectResponse:
    _check(k)
    out = scheduler.process_due()
    aviso = "publicado" if any(r.get("ok") for r in out.get("resultados") or []) else "agendado"
    return RedirectResponse(url=f"/publicar?k={k}&aviso={aviso}", status_code=303)


def _redir(k: str, aviso: str, erro: str = "") -> RedirectResponse:
    url = f"/publicar?k={k}&aviso={aviso}"
    if erro:
        url += f"&msg={quote(erro[:160])}"
    return RedirectResponse(url=url, status_code=303)


@router.post("/publicar/rmk-previas")
def mandar_rmk_previas(
    k: str = Form(...), chat_id: str = Form("")
) -> RedirectResponse:
    _check(k)
    try:
        from app.services import telegram as tg

        tg.ensure_webhook()
        if (chat_id or "").strip():
            previews.ligar_por_texto(chat_id.strip())
        if not previews.chat_id():
            return _redir(k, "grupo-nao-ligado")
        out = previews.publicar_do_funil(force=True)
        if not out.get("enviados"):
            return _redir(k, "sem-funil")
        ok = any(r.get("ok") for r in out.get("enviados") or [])
        return _redir(k, "rmk-ok" if ok else "rmk-falha")
    except Exception as erro:
        return _redir(k, "rmk-falha", str(erro))


@router.post("/publicar/ligar-previas")
def ligar_previas(k: str = Form(...), chat_id: str = Form("")) -> RedirectResponse:
    _check(k)
    try:
        from app.services import telegram as tg

        tg.ensure_webhook()
        previews.ligar_por_texto(chat_id)
        return _redir(k, "ligado")
    except Exception as erro:
        return _redir(k, "ligar-falha", str(erro))


@router.post("/publicar/descricao-previas")
def descricao_previas(
    k: str = Form(...), descricao: str = Form(""), pin: str = Form("")
) -> RedirectResponse:
    _check(k)
    try:
        previews.aplicar_canal(descricao=descricao, pin=pin == "1")
        return _redir(k, "desc-ok")
    except Exception as erro:
        return _redir(k, "ligar-falha", str(erro))


@router.post("/publicar/previa-item")
def previa_item(
    k: str = Form(...), item_id: str = Form(...), caption: str = Form("")
) -> RedirectResponse:
    _check(k)
    try:
        if not previews.chat_id():
            return _redir(k, "grupo-nao-ligado")
        previews.publicar_um(item_id, caption)
        return _redir(k, "item-ok")
    except Exception as erro:
        return _redir(k, "item-falha", str(erro))


_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px 16px 64px;
  background: #0f0f12; color: #f2f2f5;
  font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.wrap { max-width: 640px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 14px; text-transform: uppercase; letter-spacing: .06em;
     color: #74747f; margin: 28px 0 12px; }
p.sub { margin: 0 0 24px; color: #9a9aa5; font-size: 14px; }
a.nav { color: #e1306c; text-decoration: none; font-size: 14px; }
form.novo { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
textarea, input[type=password], input[type=text], input[type=url],
input[type=datetime-local], select, input[type=file] {
  width: 100%; padding: 14px; border-radius: 12px;
  border: 1px solid #2c2c33; background: #17171c; color: #f2f2f5;
  font: inherit;
}
textarea:focus, input:focus, select:focus { outline: 2px solid #e1306c; border-color: transparent; }
button {
  padding: 14px; border: 0; border-radius: 12px; font: inherit; font-weight: 600;
  background: #e1306c; color: #fff; cursor: pointer;
}
button.ghost { background: #23232a; color: #cfcfd6; font-weight: 500; }
button.link {
  background: none; color: #74747f; padding: 4px 8px; font-size: 13px; font-weight: 500;
}
.row { display: flex; gap: 8px; }
.row > * { flex: 1; }
.aviso { border-radius: 12px; padding: 12px 14px; font-size: 14px; margin-bottom: 18px; }
.aviso.ok { background: #13291d; color: #7ee2a8; }
.aviso.erro { background: #2b1a1a; color: #f0a19a; }
.aviso.info { background: #1a1a2b; color: #a8b4f0; }
ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
li { background: #17171c; border: 1px solid #22222a; border-radius: 12px; padding: 12px 14px;
     display: flex; align-items: flex-start; gap: 10px; }
li .txt { flex: 1; min-width: 0; word-break: break-word; }
li .quando { display: block; color: #74747f; font-size: 12px; margin-top: 4px; }
.tag { font-size: 11px; padding: 2px 7px; border-radius: 99px; background: #2a2a33;
       color: #a0a0ab; margin-left: 6px; vertical-align: middle; }
.tag.pending { background: #2a2418; color: #e6c07b; }
.tag.published { background: #13291d; color: #7ee2a8; }
.tag.failed { background: #2b1a1a; color: #f0a19a; }
.tag.cancelled { background: #222; color: #888; }
.vazio { color: #74747f; font-size: 14px; }
.hint { color: #74747f; font-size: 12px; margin: -4px 0 0; }
.card { background: #17171c; border: 1px solid #22222a; border-radius: 14px;
        padding: 14px; margin-bottom: 12px; }
.card video, .card img { width: 100%; max-height: 280px; border-radius: 10px;
        background: #000; margin-bottom: 10px; }
.cta { font-size: 13px; color: #e6c07b; word-break: break-all; }
"""


def _login() -> str:
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Publicar</title><style>{_CSS}</style></head>
<body><div class="wrap">
  <h1>Publicar</h1>
  <p class="sub">Programar feed, reels e stories.</p>
  <form class="novo" method="get" action="/publicar">
    <input type="password" name="k" placeholder="senha" autofocus>
    <button type="submit">Entrar</button>
  </form>
</div></body></html>"""


def _faixa_previas() -> str:
    info = previews.status()
    tom = "ok" if info.get("ok") else "info"
    return f'<div class="aviso {tom}">{html.escape(info["texto"])}</div>'


def _bloco_previas(k: str) -> str:
    seguro = html.escape(k)
    ck = html.escape(previews.checkout_url())
    botao = html.escape(previews._markup_vip()["inline_keyboard"][0][0]["text"])
    desc = html.escape(previews.descricao_canal())
    pin = html.escape(previews._boas_vindas())
    ligado = bool(previews.chat_id())
    cards = []
    for item in previews.painel_itens():
        iid = html.escape(item["id"])
        url = html.escape(item["url"])
        cap = html.escape(item["caption"])
        kind = html.escape(item["kind"])
        media = ""
        if item["url"] and item["kind"] == "vídeo":
            media = f'<video src="{url}" controls preload="metadata"></video>'
        elif item["url"]:
            media = f'<img src="{url}" alt="">'
        elif not item["url"]:
            media = '<p class="hint">Mídia só no Telegram (file_id). Publica pelo botão mesmo assim.</p>'
        cards.append(
            f"""<div class="card">
              <strong>{kind} · {iid}</strong>
              {media}
              <form class="novo" method="post" action="/publicar/previa-item">
                <input type="hidden" name="k" value="{seguro}">
                <input type="hidden" name="item_id" value="{iid}">
                <textarea name="caption" rows="6">{cap}</textarea>
                <p class="hint cta">CTA: {botao} → {ck}</p>
                <button type="submit">Publicar esta no canal</button>
              </form>
            </div>"""
        )
    lista = "".join(cards) or '<p class="vazio">Sem mídia no funil. Sobe vídeo no /fluxo.</p>'
    ligar = ""
    if not ligado:
        ligar = f"""
  <form class="novo" method="post" action="/publicar/ligar-previas">
    <input type="hidden" name="k" value="{seguro}">
    <input type="text" name="chat_id" placeholder="@seucanal ou https://t.me/seucanal ou id -100…">
    <p class="hint">O id da URL do Web K quase nunca funciona. Melhor: username público
    do canal, ou encaminha um post do canal pro
    <a class="nav" href="https://t.me/liviagommes_bot">@liviagommes_bot</a>
    e atualiza esta página.</p>
    <button type="submit">Ligar canal de prévias</button>
  </form>
  <p class="hint">Pra o site postar, o @liviagommes_bot tem que ser admin com Post messages.
  <a class="nav" href="https://t.me/liviagommes_bot?startchannel=true&amp;admin=post_messages">Adicionar o bot no canal</a></p>
"""
    return f"""
  <h2>Canal de prévias</h2>
  {_faixa_previas()}
  <p class="hint">Checkout: {ck} · Botão: {botao}</p>
  {ligar}
  <form class="novo" method="post" action="/publicar/descricao-previas">
    <input type="hidden" name="k" value="{seguro}">
    <textarea name="descricao" rows="3" maxlength="255">{desc}</textarea>
    <p class="hint">Até 255 caracteres. Vai na bio do canal.</p>
    <label class="hint"><input type="checkbox" name="pin" value="1" checked>
      Também pinar o texto de boas-vindas com CTA</label>
    <button class="ghost" type="submit">Aplicar descrição no canal</button>
  </form>
  <div class="card"><p style="white-space:pre-wrap;margin:0;font-size:14px">{pin}</p></div>
  {lista}
  <form method="post" action="/publicar/rmk-previas" style="margin-bottom:24px">
    <input type="hidden" name="k" value="{seguro}">
    <button type="submit" style="width:100%">Publicar todas as prévias agora</button>
  </form>
"""


def _fmt_quando(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            return valor
    try:
        return valor.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(valor)


def _lista(k: str) -> str:
    itens = schedule.list_recent(limit=40)
    if not itens:
        return '<p class="vazio">Nada agendado ainda.</p>'
    linhas = []
    for item in itens:
        status = item.get("status") or "?"
        erro = html.escape(item.get("error") or "")
        rotulo = {
            "previas": "prévias TG",
            "story": "story IG",
            "feed": "feed IG",
            "reels": "reel IG",
        }.get(item.get("kind") or "", item.get("kind") or "")
        caption = html.escape((item.get("caption") or "")[:120])
        url = html.escape(item.get("media_url") or "")
        linhas.append(
            f"""<li>
              <span class="txt">
                <strong>{html.escape(rotulo)}</strong>
                <span class="tag {html.escape(status)}">{html.escape(status)}</span>
                <span class="quando">{_fmt_quando(item.get('scheduled_for'))}</span>
                {f'<span class="quando">{caption}</span>' if caption else ''}
                <span class="quando" style="word-break:break-all">{url}</span>
                {f'<span class="quando" style="color:#f0a19a">{erro}</span>' if erro else ''}
              </span>
              {"<form method='post' action='/publicar/cancelar'>"
               f"<input type='hidden' name='k' value='{html.escape(k)}'>"
               f"<input type='hidden' name='id' value='{html.escape(item['id'])}'>"
               "<button class='link' type='submit'>cancelar</button></form>"
               if status in {"pending", "failed"} else ""}
            </li>"""
        )
    return f"<ul>{''.join(linhas)}</ul>"


def _page(k: str, aviso: str = "", msg: str = "") -> str:
    seguro = html.escape(k)
    tom, texto = _AVISOS.get(aviso, ("", ""))
    extra = html.escape(msg) if msg else ""
    faixa = ""
    if texto or extra:
        corpo = texto + (f" {extra}" if extra else "")
        faixa = f'<div class="aviso {tom or "info"}">{corpo}</div>'
    agora_local = datetime.now(FUSO).strftime("%Y-%m-%dT%H:%M")
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Publicar</title><style>{_CSS}</style></head>
<body><div class="wrap">
  <p><a class="nav" href="/diario?k={seguro}">← diário</a>
     · <a class="nav" href="/fluxo?k={seguro}">funil</a></p>
  <h1>Publicar</h1>
  <p class="sub">Canal de prévias no Telegram (vídeo, descrição, CTA) e
  Instagram. Prévias nunca misturam com o chat pessoal nem com o VIP.</p>

  {faixa}
  {_bloco_previas(k)}

  <h2>Instagram e extra</h2>
  <form class="novo" method="post" action="/publicar" enctype="multipart/form-data">
    <input type="hidden" name="k" value="{seguro}">
    <select name="kind" required>
      <option value="previas">Grupo de prévias (Telegram)</option>
      <option value="story">Story no Instagram</option>
      <option value="feed">Post no feed (foto)</option>
      <option value="reels">Reel no Instagram</option>
    </select>
    <input type="file" name="arquivo" accept="image/jpeg,image/png,image/*,video/mp4,video/*">
    <p class="hint">Upload até 4 MB (foto/story). Reel grande: cole a URL abaixo.</p>
    <input type="url" name="media_url" placeholder="ou cole URL pública https://...">
    <textarea name="caption" rows="2" placeholder="legenda — no Telegram pode ser só texto, sem mídia"></textarea>
    <input type="datetime-local" name="quando" value="{agora_local}" required>
    <div class="row">
      <button type="submit">Agendar</button>
      <button class="ghost" type="submit" name="agora" value="1">Publicar agora</button>
    </div>
  </form>

  <form method="post" action="/publicar/rodar" style="margin-bottom:24px">
    <input type="hidden" name="k" value="{seguro}">
    <button class="ghost" type="submit" style="width:100%">
      Publicar o que já passou da hora
    </button>
  </form>

  <h2>Fila</h2>
  {_lista(k)}
</div></body></html>"""
