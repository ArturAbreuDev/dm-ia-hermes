from __future__ import annotations

import html
import uuid

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import get_settings
from app.services import instagram, stories
from app.store import memory, runtime, story_context

router = APIRouter(include_in_schema=False)


def _check(senha: str) -> None:
    configurada = get_settings().diary_password
    if not configurada:
        raise HTTPException(
            status_code=503,
            detail="Defina DIARY_PASSWORD nas variáveis de ambiente para usar o diário",
        )
    if senha != configurada:
        raise HTTPException(status_code=403, detail="Senha incorreta")


@router.get("/diario", response_class=HTMLResponse)
def diario(k: str = "", aviso: str = "") -> HTMLResponse:
    if not k:
        return HTMLResponse(_login_page())
    _check(k)
    return HTMLResponse(_page(k, aviso))


@router.post("/diario")
def adicionar(k: str = Form(...), texto: str = Form(...)) -> RedirectResponse:
    _check(k)
    limpo = texto.strip()
    if limpo:
        story_context.save(f"nota-{uuid.uuid4().hex[:12]}", limpo, kind="nota")
    return RedirectResponse(url=f"/diario?k={k}", status_code=303)


@router.post("/diario/apagar")
def apagar(k: str = Form(...), id: str = Form(...)) -> RedirectResponse:
    _check(k)
    story_context.delete(id)
    return RedirectResponse(url=f"/diario?k={k}", status_code=303)


@router.post("/diario/sincronizar")
def sincronizar(k: str = Form(...)) -> RedirectResponse:
    _check(k)
    stories.sync_active_stories()
    return RedirectResponse(url=f"/diario?k={k}", status_code=303)


# Avisos são código, não texto vindo do formulário: nada do que a pessoa digita
# volta para o HTML.
_AVISOS = {
    "bloqueado": ("ok", "Pronto, ela não fala mais com essa pessoa."),
    "nao-achei": (
        "erro",
        "Não achei esse @ nas conversas. Confira a grafia — só dá para "
        "bloquear quem já mandou DM alguma vez.",
    ),
    "liberado": ("ok", "Liberado. Ela volta a responder essa pessoa."),
    "checkout-straton": ("ok", "Checkout da Straton ativo. As DMs vão mandar o bot do Telegram."),
    "checkout-botgram": ("ok", "Checkout do Botgram ativo. As DMs vão mandar a página de planos."),
    "checkout-invalido": ("erro", "Escolha Straton ou Botgram."),
}


@router.post("/diario/checkout")
def escolher_checkout(k: str = Form(...), provider: str = Form(...)) -> RedirectResponse:
    _check(k)
    escolhido = (provider or "").strip().lower()
    if escolhido not in {"straton", "botgram"}:
        return RedirectResponse(url=f"/diario?k={k}&aviso=checkout-invalido", status_code=303)
    runtime.set("checkout_provider", escolhido)
    return RedirectResponse(url=f"/diario?k={k}&aviso=checkout-{escolhido}", status_code=303)


@router.post("/diario/bloquear")
def bloquear(k: str = Form(...), arroba: str = Form(...)) -> RedirectResponse:
    _check(k)
    limpo = arroba.strip().lstrip("@")
    if not limpo:
        return RedirectResponse(url=f"/diario?k={k}", status_code=303)

    igsid = instagram.find_igsid_by_username(limpo)
    if not igsid:
        return RedirectResponse(url=f"/diario?k={k}&aviso=nao-achei", status_code=303)

    memory.set_muted(igsid, True)
    memory.remember_username(igsid, limpo)
    return RedirectResponse(url=f"/diario?k={k}&aviso=bloqueado", status_code=303)


@router.post("/diario/liberar")
def liberar(k: str = Form(...), igsid: str = Form(...)) -> RedirectResponse:
    _check(k)
    memory.set_muted(igsid, False)
    return RedirectResponse(url=f"/diario?k={k}&aviso=liberado", status_code=303)


_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px 16px 64px;
  background: #0f0f12; color: #f2f2f5;
  font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.wrap { max-width: 560px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; }
p.sub { margin: 0 0 24px; color: #9a9aa5; font-size: 14px; }
form.novo { display: flex; flex-direction: column; gap: 10px; margin-bottom: 28px; }
textarea, input[type=password], input[type=text] {
  width: 100%; padding: 14px; border-radius: 12px;
  border: 1px solid #2c2c33; background: #17171c; color: #f2f2f5;
  font: inherit; resize: vertical;
}
textarea:focus, input:focus { outline: 2px solid #e1306c; border-color: transparent; }
button {
  padding: 14px; border: 0; border-radius: 12px; font: inherit; font-weight: 600;
  background: #e1306c; color: #fff; cursor: pointer;
}
button.ghost { background: #23232a; color: #cfcfd6; font-weight: 500; }
button.link {
  background: none; color: #74747f; padding: 4px 8px; font-size: 13px; font-weight: 500;
}
h2 { font-size: 14px; text-transform: uppercase; letter-spacing: .06em;
     color: #74747f; margin: 28px 0 12px; }
ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
li { background: #17171c; border: 1px solid #22222a; border-radius: 12px; padding: 12px 14px;
     display: flex; align-items: flex-start; gap: 10px; }
li .txt { flex: 1; }
li .quando { display: block; color: #74747f; font-size: 12px; margin-top: 4px; }
.vazio { color: #74747f; font-size: 14px; }
.tag { font-size: 11px; padding: 2px 7px; border-radius: 99px; background: #2a2a33;
       color: #a0a0ab; margin-left: 6px; vertical-align: middle; }
.aviso { border-radius: 12px; padding: 12px 14px; font-size: 14px; margin-bottom: 18px; }
.aviso.ok { background: #13291d; color: #7ee2a8; }
.aviso.erro { background: #2b1a1a; color: #f0a19a; }
.arroba { font-variant-numeric: tabular-nums; }
form.inline { display: flex; gap: 8px; }
form.inline input { flex: 1; }
form.inline button { width: auto; padding: 14px 18px; white-space: nowrap; }
.opcoes { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.opcao {
  display: flex; align-items: flex-start; gap: 12px;
  background: #17171c; border: 1px solid #22222a; border-radius: 12px;
  padding: 12px 14px; cursor: pointer;
}
.opcao:has(input:checked) { border-color: #e1306c; background: #1c1418; }
.opcao input { margin-top: 3px; accent-color: #e1306c; }
.opcao .nome { font-weight: 600; }
.opcao .detalhe { display: block; color: #9a9aa5; font-size: 13px; margin-top: 2px; word-break: break-all; }
"""


def _login_page() -> str:
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Diário da Lívia</title><style>{_CSS}</style></head>
<body><div class="wrap">
  <h1>Diário da Lívia</h1>
  <p class="sub">Digite a senha para continuar.</p>
  <form class="novo" method="get" action="/diario">
    <input type="password" name="k" placeholder="senha" autofocus>
    <button type="submit">Entrar</button>
  </form>
</div></body></html>"""


def _bloco_bloqueio(k: str) -> str:
    """Lista de quem está silenciado, com o @ quando a gente já sabe qual é."""
    linhas = []
    for igsid, lead in memory.muted_leads():
        arroba = lead.get("username")
        if not arroba:
            arroba = instagram.get_user_profile(igsid).get("username")
        quem = f"@{arroba}" if arroba else igsid
        linhas.append(
            f"""<li>
              <span class="txt arroba">{html.escape(quem)}</span>
              <form method="post" action="/diario/liberar">
                <input type="hidden" name="k" value="{html.escape(k)}">
                <input type="hidden" name="igsid" value="{html.escape(igsid)}">
                <button class="link" type="submit">liberar</button>
              </form>
            </li>"""
        )
    if linhas:
        return f"<ul>{''.join(linhas)}</ul>"
    return '<p class="vazio">Ninguém bloqueado.</p>'


def _bloco_checkout(k: str) -> str:
    settings = get_settings()
    ativo = settings.checkout_provider()
    straton_url = html.escape(settings.checkout_url_straton or "")
    botgram_url = html.escape(settings.checkout_url_botgram or "")
    check_s = "checked" if ativo == "straton" else ""
    check_b = "checked" if ativo == "botgram" else ""
    return f"""
  <h2>Checkout</h2>
  <p class="sub" style="margin-bottom:12px">Qual link ela manda nas DMs e no
  disparo. A troca vale na hora, sem precisar subir de novo.</p>
  <form method="post" action="/diario/checkout">
    <input type="hidden" name="k" value="{html.escape(k)}">
    <div class="opcoes">
      <label class="opcao">
        <input type="radio" name="provider" value="straton" {check_s}>
        <span>
          <span class="nome">Straton (Telegram)</span>
          <span class="detalhe">CTA /vip abre @{html.escape(settings.telegram_vip_bot())} · PIX Straton · R$ {html.escape(settings.price_straton)}</span>
        </span>
      </label>
      <label class="opcao">
        <input type="radio" name="provider" value="botgram" {check_b}>
        <span>
          <span class="nome">Botgram (planos)</span>
          <span class="detalhe">{botgram_url} · R$ {html.escape(settings.price_botgram)}</span>
        </span>
      </label>
    </div>
    <button type="submit" style="width:100%">Usar este checkout</button>
  </form>
"""


def _page(k: str, aviso: str = "") -> str:
    itens = story_context.recent(limit=30)
    if itens:
        linhas = "".join(
            f"""<li>
              <span class="txt">{html.escape(item['description'])}
                <span class="quando">{item['quando']}"""
            + (
                '<span class="tag">story</span>'
                if item["kind"] == "story"
                else '<span class="tag">anotado</span>'
            )
            + f"""</span>
              </span>
              <form method="post" action="/diario/apagar">
                <input type="hidden" name="k" value="{html.escape(k)}">
                <input type="hidden" name="id" value="{html.escape(item['id'])}">
                <button class="link" type="submit">apagar</button>
              </form>
            </li>"""
            for item in itens
        )
        lista = f"<ul>{linhas}</ul>"
    else:
        lista = '<p class="vazio">Nada anotado ainda.</p>'

    seguro = html.escape(k)
    tom, texto = _AVISOS.get(aviso, ("", ""))
    faixa = f'<div class="aviso {tom}">{texto}</div>' if texto else ""
    bloqueados = _bloco_bloqueio(k)
    checkout = _bloco_checkout(k)
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Diário da Lívia</title><style>{_CSS}</style></head>
<body><div class="wrap">
  <h1>Diário da Lívia</h1>
  <p class="sub">Escreva o que você fez, do seu jeito. A Lívia do Instagram vai
  responder as DMs sabendo disso. Cada anotação vale por 7 dias.
  <a href="/publicar?k={seguro}" style="color:#e1306c">Programar posts / prévias →</a>
  <a href="/fluxo?k={seguro}" style="color:#e1306c;margin-left:12px">Funil do bot →</a>
  <a href="/pedidos?k={seguro}" style="color:#e1306c;margin-left:12px">Pedidos →</a>
  <a href="/linktree?k={seguro}" style="color:#e1306c;margin-left:12px">Linktree →</a></p>

  {faixa}

  {checkout}

  <form class="novo" method="post" action="/diario">
    <input type="hidden" name="k" value="{seguro}">
    <textarea name="texto" rows="3" required
      placeholder="ex: fui na Expointer ver os animais e comi churros"></textarea>
    <button type="submit">Anotar</button>
  </form>

  <form method="post" action="/diario/sincronizar">
    <input type="hidden" name="k" value="{seguro}">
    <button class="ghost" type="submit" style="width:100%">
      Puxar os stories que estão no ar agora
    </button>
  </form>

  <h2>Não responder</h2>
  <p class="sub" style="margin-bottom:12px">Coloque o @ de quem ela deve deixar
  de responder. Se a pessoa falar que vai pagar, ela responde mesmo assim.</p>
  <form class="inline" method="post" action="/diario/bloquear"
        style="margin-bottom:12px">
    <input type="hidden" name="k" value="{seguro}">
    <input type="text" name="arroba" placeholder="@ da pessoa"
           autocapitalize="off" autocomplete="off" spellcheck="false" required>
    <button type="submit">Bloquear</button>
  </form>
  {bloqueados}

  <h2>O que ela sabe</h2>
  {lista}
</div></body></html>"""
