"""Linktree da Lívia (bio do Instagram) e página do PIX."""

from __future__ import annotations

from html import escape
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.config import ROOT_DIR, get_settings
from app.services import funnel, ig_checkout, previews
from app.store import linktree

router = APIRouter(include_in_schema=False)

_COVER = ROOT_DIR / "assets" / "telegram" / "cover.jpg"

_TG_SVG = (
    '<svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">'
    '<path fill="#fff" d="M21.9 4.1 2.8 11.5c-1.3.5-1.3 1.2-.2 1.5l4.9 1.5 11.4-7.2c.5-.3.9-.1.5.2'
    'L9.2 14.8l-.4 4.7c.5 0 .7-.2 1-.5l2.1-2 4.3 3.1c.8.5 1.4.2 1.6-.7l3.7-14.5c.4-1.5-.5-2.2-1.6-1.8z"/>'
    "</svg>"
)
_IG_SVG = (
    '<svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">'
    '<path fill="none" stroke="#111" stroke-width="1.8" '
    'd="M8 3.5h8A4.5 4.5 0 0 1 20.5 8v8a4.5 4.5 0 0 1-4.5 4.5H8A4.5 4.5 0 0 1 3.5 16V8A4.5 4.5 0 0 1 8 3.5z"/>'
    '<circle cx="12" cy="12" r="3.6" fill="none" stroke="#111" stroke-width="1.8"/>'
    '<circle cx="17.2" cy="6.8" r="1" fill="#111"/></svg>'
)
_PRIVACY_SVG = (
    '<svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">'
    '<text x="16" y="22" text-anchor="middle" font-size="18" font-weight="800" '
    'font-family="system-ui,sans-serif" fill="#fff">P</text></svg>'
)


@router.get("/vip/cover.jpg")
def capa() -> FileResponse:
    if not _COVER.exists():
        from fastapi import HTTPException

        raise HTTPException(status_code=404)
    return FileResponse(_COVER, media_type="image/jpeg")


@router.get("/links", response_class=HTMLResponse)
@router.get("/vip", response_class=HTMLResponse)
def vip() -> HTMLResponse:
    return HTMLResponse(_tree())


def _check(senha: str) -> None:
    configurada = get_settings().diary_password
    if not configurada:
        raise HTTPException(status_code=503, detail="Defina DIARY_PASSWORD")
    if senha != configurada:
        raise HTTPException(status_code=403, detail="Senha incorreta")


@router.get("/linktree", response_class=HTMLResponse)
def editar_linktree(k: str = "", ok: str = "") -> HTMLResponse:
    if not k:
        return HTMLResponse(_login_editar())
    _check(k)
    return HTMLResponse(_pagina_editar(k, ok=ok == "1"))


@router.post("/linktree")
def salvar_linktree(
    k: str = Form(...),
    tagline: str = Form(""),
    instagram: str = Form(""),
    titulo: list[str] = Form(default=[]),
    desc: list[str] = Form(default=[]),
    url: list[str] = Form(default=[]),
    kind: list[str] = Form(default=[]),
) -> RedirectResponse:
    _check(k)
    n = max(len(titulo), len(desc), len(url), len(kind))
    botoes = []
    for i in range(n):
        botoes.append(
            {
                "titulo": titulo[i] if i < len(titulo) else "",
                "desc": desc[i] if i < len(desc) else "",
                "url": url[i] if i < len(url) else "",
                "kind": kind[i] if i < len(kind) else "foto",
            }
        )
    linktree.salvar(tagline=tagline, instagram=instagram, botoes=botoes)
    return RedirectResponse(url=f"/linktree?k={k}&ok=1", status_code=303)


@router.get("/pix/{slug}", response_class=HTMLResponse)
def pix(slug: str) -> HTMLResponse:
    dados = ig_checkout.dados_do_slug(slug)
    codigo = str(dados.get("codigo") or "").strip()
    if not codigo:
        raise HTTPException(status_code=404, detail="PIX não encontrado")
    preco = escape(str(dados.get("preco") or ""))
    pago = bool(dados.get("pago"))
    qr = str(dados.get("qr") or "")
    if not qr.startswith("http"):
        qr = "https://api.qrserver.com/v1/create-qr-code/?size=280x280&data=" + quote(codigo)
    status = "já caiu 🔥" if pago else f"R$ {preco}"
    return HTMLResponse(_pix_html(escape(codigo), escape(qr), status, pago))


def _foto(settings) -> str:
    perfil = funnel.banner()
    capa = str(perfil.get("photo_url") or "").strip()
    if capa.startswith("http"):
        return capa
    if settings.base_url:
        return f"{settings.base_url}/vip/cover.jpg"
    return "/vip/cover.jpg"


def _ico(kind: str, capa: str) -> str:
    if kind == "tg":
        return _TG_SVG
    if kind == "privacy":
        return _PRIVACY_SVG
    if kind == "ig":
        return _IG_SVG.replace("#111", "#fff")
    return f'<img src="{escape(capa)}" alt="">'


def _botoes(capa: str) -> list[dict[str, str]]:
    cfg = linktree.carregar()
    convite = previews.convite_publico()
    out: list[dict[str, str]] = []
    for item in cfg["botoes"]:
        href = (item.get("url") or "").strip()
        titulo = item.get("titulo") or ""
        if not href and "previa" in titulo.lower().replace("é", "e"):
            href = convite
        if not href:
            continue
        kind = item.get("kind") or "foto"
        out.append(
            {
                "href": href,
                "kind": kind,
                "titulo": titulo,
                "desc": item.get("desc") or "",
                "ico": _ico(kind, capa),
            }
        )
    return out


def _tree() -> str:
    settings = get_settings()
    bot = settings.telegram_vip_bot()
    perfil = funnel.banner()
    cfg = linktree.carregar()
    nome = escape(perfil.get("name") or settings.business_name or "Lívia Gomes")
    capa = escape(_foto(settings))
    handle = (cfg.get("instagram") or settings.instagram_handle or "").strip().lstrip("@")
    ig = f"https://instagram.com/{handle}" if handle else ""
    botoes = _botoes(capa)
    linhas = []
    for i, b in enumerate(botoes):
        extra = ' id="abrir"' if i == 0 and "t.me/" in (b.get("href") or "") else ""
        desc = (
            f'<span class="dsc">{escape(b["desc"])}</span>' if b.get("desc") else ""
        )
        linhas.append(
            f'<a class="btn" rel="noopener"{extra} href="{escape(b["href"])}">'
            f'<span class="ico {escape(b["kind"])}">{b["ico"]}</span>'
            f'<span class="txt"><span class="ttl">{escape(b["titulo"])}</span>{desc}</span>'
            f'<span class="dots" aria-hidden="true"><i></i><i></i><i></i></span></a>'
        )
    ig_html = (
        f'<a class="ig" href="{escape(ig)}" rel="noopener" aria-label="Instagram">{_IG_SVG}</a>'
        if ig
        else f'<span class="ig">{_IG_SVG}</span>'
    )
    web = f"https://t.me/{bot}"
    tg = f"tg://resolve?domain={bot}"
    intent = (
        f"intent://resolve?domain={bot}#Intent;scheme=tg;"
        "package=org.telegram.messenger;end"
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{nome}</title>
<meta name="description" content="{escape(cfg.get('tagline') or 'Descobriu meu segredinho')}">
<meta property="og:title" content="{nome}">
<meta property="og:image" content="{capa}">
<meta property="og:type" content="website">
<meta name="theme-color" content="#ececec">
<style>
* {{ box-sizing: border-box; }}
body {{
  margin: 0; min-height: 100dvh; background: #ececec; color: #111;
  font: 16px/1.35 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}}
.wrap {{
  max-width: 430px; margin: 0 auto;
  padding: 52px 22px 64px; text-align: center;
}}
.avatar {{
  width: 168px; height: 168px; object-fit: cover; object-position: center;
  border-radius: 28px; border: 5px solid #6d8cff;
  box-shadow: 0 10px 28px rgba(80,110,255,.28);
  background: #111;
}}
h1 {{
  font-size: 34px; font-weight: 800; letter-spacing: -.04em;
  margin: 22px 0 8px;
}}
.sub {{ color: #6a6a73; font-size: 16.5px; margin: 0 0 16px; }}
.ig {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 40px; height: 40px; margin: 0 0 22px; color: #111;
}}
.btn {{
  display: flex; align-items: center; gap: 12px;
  background: #111; color: #fff; text-decoration: none;
  border-radius: 999px; padding: 10px 16px 10px 10px;
  margin: 0 0 12px; min-height: 72px; text-align: left;
  box-shadow: 0 1px 0 rgba(255,255,255,.08) inset;
}}
.btn .ico {{
  width: 52px; height: 52px; border-radius: 50%; flex-shrink: 0;
  display: grid; place-items: center; overflow: hidden; background: #222;
}}
.btn .ico.tg {{ background: #2aa3e0; }}
.btn .ico.privacy {{ background: #ff5a1f; }}
.btn .ico img {{ width: 100%; height: 100%; object-fit: cover; }}
.btn .txt {{ flex: 1; min-width: 0; }}
.btn .ttl {{ display: block; font-weight: 800; font-size: 15px; letter-spacing: .01em; }}
.btn .dsc {{ display: block; margin-top: 2px; font-size: 13px; color: #c5c5c8; font-weight: 500; }}
.dots {{
  display: flex; flex-direction: column; gap: 3px; flex-shrink: 0; padding: 0 4px;
}}
.dots i {{
  display: block; width: 3.5px; height: 3.5px; border-radius: 50%; background: #fff; opacity: .55;
}}
</style>
</head>
<body>
  <div class="wrap">
    <img class="avatar" src="{capa}" alt="{nome}">
    <h1>{nome}</h1>
    <p class="sub">{escape(cfg.get("tagline") or "Descobriu meu segredinho 😉")}</p>
    {ig_html}
    {''.join(linhas)}
  </div>
  <script>
    (function () {{
      var tg = {tg!r};
      var web = {web!r};
      var intent = {intent!r};
      var android = /Android/i.test(navigator.userAgent || "");
      var btn = document.getElementById("abrir");
      if (!btn) return;
      if (android) btn.href = intent;
      btn.addEventListener("click", function (e) {{
        e.preventDefault();
        window.location.href = android ? intent : tg;
        setTimeout(function () {{ window.location.href = web; }}, 1200);
      }});
    }})();
  </script>
</body>
</html>"""


def _login_editar() -> str:
    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Linktree</title>
<style>
body { margin:0; padding:24px; background:#0f0f12; color:#f2f2f5;
  font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
.wrap { max-width:420px; margin:0 auto; }
input,button { width:100%; padding:14px; border-radius:12px; font:inherit; }
input { border:1px solid #2c2c33; background:#17171c; color:#fff; }
button { border:0; background:#e1306c; color:#fff; font-weight:600; margin-top:10px; }
</style></head>
<body><div class="wrap">
  <h1>Linktree</h1>
  <form method="get" action="/linktree">
    <input type="password" name="k" placeholder="senha" autofocus>
    <button type="submit">Entrar</button>
  </form>
</div></body></html>"""


def _pagina_editar(k: str, *, ok: bool = False) -> str:
    cfg = linktree.carregar()
    seguro = escape(k)
    faixa = '<div class="aviso">Salvo. Já aparece no /vip.</div>' if ok else ""
    blocos = []
    for b in cfg["botoes"]:
        blocos.append(_bloco_botao(b))
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Editar linktree</title>
<style>
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 24px 16px 80px; background: #0f0f12; color: #f2f2f5;
  font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ max-width: 560px; margin: 0 auto; }}
a {{ color: #e1306c; text-decoration: none; }}
h1 {{ font-size: 22px; margin: 0 0 4px; }}
p.sub {{ color: #9a9aa5; font-size: 14px; margin: 0 0 20px; }}
label {{ display:block; font-size:12px; color:#74747f; margin: 8px 0 4px; }}
input, select {{
  width: 100%; padding: 12px; border-radius: 12px; font: inherit;
  border: 1px solid #2c2c33; background: #17171c; color: #f2f2f5;
}}
button {{
  padding: 14px; border: 0; border-radius: 12px; font: inherit; font-weight: 600;
  background: #e1306c; color: #fff; cursor: pointer; width: 100%;
}}
button.ghost {{ background: #23232a; color: #cfcfd6; font-weight: 500; margin-top: 8px; }}
button.link {{ background: none; color: #f0a19a; width: auto; padding: 4px 0; }}
.card {{
  background: #17171c; border: 1px solid #22222a; border-radius: 16px;
  padding: 14px; margin-bottom: 12px;
}}
.aviso {{ background: #13291d; color: #7ee2a8; border-radius: 12px; padding: 12px; margin-bottom: 16px; }}
</style></head>
<body><div class="wrap">
  <p><a href="/diario?k={seguro}">← diário</a>
     · <a href="/vip" target="_blank">ver página</a></p>
  <h1>Linktree</h1>
  <p class="sub">Muda o texto, o link e o ícone de cada botão. Vale na hora, sem deploy.</p>
  {faixa}
  <form method="post" action="/linktree" id="form">
    <input type="hidden" name="k" value="{seguro}">
    <label>Frase embaixo do nome</label>
    <input type="text" name="tagline" value="{escape(cfg.get('tagline') or '')}">
    <label>@ do Instagram (ícone)</label>
    <input type="text" name="instagram" placeholder="sem @" value="{escape(cfg.get('instagram') or '')}">
    <h2 style="font-size:14px;color:#74747f;margin:24px 0 8px">BOTÕES</h2>
    <div id="lista">{''.join(blocos)}</div>
    <button class="ghost" type="button" id="add">+ botão</button>
    <button type="submit" style="margin-top:12px">Salvar</button>
  </form>
</div>
<template id="tpl">{_bloco_botao({"titulo":"","desc":"","url":"","kind":"foto"})}</template>
<script>
document.getElementById("add").onclick = function () {{
  var t = document.getElementById("tpl");
  document.getElementById("lista").appendChild(t.content.cloneNode(true));
}};
document.getElementById("lista").addEventListener("click", function (e) {{
  if (e.target.classList.contains("tirar")) e.target.closest(".card").remove();
}});
</script>
</body></html>"""


def _bloco_botao(b: dict) -> str:
    kind = escape(b.get("kind") or "foto")
    opts = []
    for valor, nome in (("tg", "Telegram"), ("foto", "Foto"), ("privacy", "Privacy"), ("ig", "Instagram")):
        sel = " selected" if kind == valor else ""
        opts.append(f'<option value="{valor}"{sel}>{nome}</option>')
    return f"""<div class="card">
      <label>Título do botão</label>
      <input type="text" name="titulo" value="{escape(b.get('titulo') or '')}" placeholder="CANAL VIP 🔥">
      <label>Linha de baixo</label>
      <input type="text" name="desc" value="{escape(b.get('desc') or '')}" placeholder="Fotos e vídeos sem censura">
      <label>Link</label>
      <input type="url" name="url" value="{escape(b.get('url') or '')}" placeholder="https://t.me/...">
      <label>Ícone</label>
      <select name="kind">{''.join(opts)}</select>
      <button class="link tirar" type="button">tirar botão</button>
    </div>"""


def _pix_html(codigo: str, qr: str, status: str, pago: bool) -> str:
    acao = "já pago" if pago else "copiar código"
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>PIX — Priv da Lívia</title>
<meta name="theme-color" content="#0f0f12">
<style>
* {{ box-sizing: border-box; }}
body {{
  margin: 0; min-height: 100dvh;
  background: #0f0f12; color: #f2f2f5;
  font: 17px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  display: flex; align-items: center; justify-content: center;
  padding: 24px 16px 40px;
}}
.card {{ max-width: 420px; width: 100%; text-align: center; }}
img.qr {{
  width: 220px; height: 220px; object-fit: contain;
  background: #fff; border-radius: 16px; padding: 10px; margin: 8px auto 18px;
}}
h1 {{ font-size: 24px; margin: 0 0 6px; }}
p {{ color: #b8b8c2; margin: 0 0 16px; }}
textarea {{
  width: 100%; min-height: 88px; border: 0; border-radius: 12px;
  background: #1a1a20; color: #ddd; padding: 12px; font-size: 12px;
  resize: none; word-break: break-all;
}}
button {{
  display: block; width: 100%; margin-top: 12px; padding: 16px 18px;
  border: 0; border-radius: 14px; background: #e1306c; color: #fff;
  font-weight: 700; font-size: 16px; cursor: pointer;
}}
.hint {{ font-size: 13px; color: #74747f; margin-top: 14px; }}
</style>
</head>
<body>
  <div class="card">
    <h1>PIX {status}</h1>
    <p>abre o banco, lê o QR ou cola o código.</p>
    <img class="qr" src="{qr}" alt="QR PIX">
    <textarea id="code" readonly>{codigo}</textarea>
    <button type="button" id="copiar">{acao}</button>
    <p class="hint">depois de pagar, volta no Instagram e me avisa.</p>
  </div>
  <script>
    document.getElementById("copiar").addEventListener("click", function () {{
      var t = document.getElementById("code");
      t.select();
      navigator.clipboard.writeText(t.value).then(function () {{
        document.getElementById("copiar").textContent = "copiado";
      }}).catch(function () {{
        document.execCommand("copy");
        document.getElementById("copiar").textContent = "copiado";
      }});
    }});
  </script>
</body>
</html>"""
