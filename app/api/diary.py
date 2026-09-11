from __future__ import annotations

import html
import uuid

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import get_settings
from app.services import stories
from app.store import story_context

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
def diario(k: str = "") -> HTMLResponse:
    if not k:
        return HTMLResponse(_login_page())
    _check(k)
    return HTMLResponse(_page(k))


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
textarea, input[type=password] {
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


def _page(k: str) -> str:
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
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Diário da Lívia</title><style>{_CSS}</style></head>
<body><div class="wrap">
  <h1>Diário da Lívia</h1>
  <p class="sub">Escreva o que você fez, do seu jeito. A Lívia do Instagram vai
  responder as DMs sabendo disso. Cada anotação vale por 7 dias.</p>

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

  <h2>O que ela sabe</h2>
  {lista}
</div></body></html>"""
