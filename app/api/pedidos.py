"""Lista de pedidos do nosso bot — nome, @, valor e status."""

from __future__ import annotations

import html
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.store import pedidos

router = APIRouter(include_in_schema=False)

_STATUS = {
    "start": ("START", "#6b6b78"),
    "pending": ("PIX ABERTO", "#e8b84a"),
    "paid": ("PAGO", "#32d583"),
    "expired": ("EXPIRADO", "#ff8a80"),
    "stopped": ("PAROU", "#74747f"),
}


def _check(k: str) -> None:
    senha = get_settings().diary_password
    if not senha:
        raise HTTPException(status_code=503, detail="Defina DIARY_PASSWORD")
    if k != senha:
        raise HTTPException(status_code=403, detail="Senha incorreta")


def _quando(valor) -> str:
    if not valor:
        return ""
    if isinstance(valor, datetime):
        dt = valor
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    else:
        bruto = str(valor)
        try:
            dt = datetime.fromisoformat(bruto.replace("Z", "+00:00"))
        except ValueError:
            return bruto[:16]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%d/%m/%y %H:%M")


@router.get("/pedidos", response_class=HTMLResponse)
def pagina(k: str = Query("")) -> HTMLResponse:
    if not k:
        return HTMLResponse(_login())
    _check(k)
    linhas = []
    for item in pedidos.listar(120):
        nome = html.escape(str(item.get("nome") or "—"))
        user = str(item.get("username") or "").strip()
        uid = html.escape(str(item.get("user_id") or ""))
        sub = f"@{html.escape(user)}" if user else uid
        produto = html.escape(str(item.get("produto") or "Acesso VIP"))
        origem = html.escape(str(item.get("origem") or "telegram"))
        valor = html.escape(str(item.get("amount") or get_settings().active_price()))
        st_key = str(item.get("status") or "start")
        rotulo, cor = _STATUS.get(st_key, (st_key.upper(), "#9a9aa5"))
        linhas.append(
            f"""<tr>
              <td>
                <strong>{nome}</strong>
                <span class="sub">{sub}</span>
              </td>
              <td>
                {produto}
                <span class="sub">{origem}</span>
              </td>
              <td>R$ {valor}</td>
              <td>{html.escape(_quando(item.get('created_at')))}</td>
              <td><span class="badge" style="color:{cor};border-color:{cor}">{rotulo}</span></td>
            </tr>"""
        )
    tabela = (
        "".join(linhas)
        if linhas
        else '<tr><td colspan="5" class="vazio">Nenhum Start ainda.</td></tr>'
    )
    seguro = html.escape(k)
    return HTMLResponse(
        f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pedidos</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin:0; background:#0c0c12; color:#f2f2f5;
  font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.wrap {{ max-width: 980px; margin: 0 auto; padding: 28px 16px 64px; }}
h1 {{ margin:0 0 4px; font-size: 26px; }}
.subhead {{ color:#8d8d99; margin:0 0 22px; }}
a {{ color:#e1306c; }}
table {{ width:100%; border-collapse: collapse; }}
th {{ text-align:left; font-size:11px; letter-spacing:.08em; color:#74747f;
  text-transform:uppercase; padding:10px 8px; border-bottom:1px solid #23232c; }}
td {{ padding:14px 8px; border-bottom:1px solid #1c1c24; vertical-align:top; }}
td strong {{ display:block; }}
td .sub {{ display:block; color:#8d8d99; font-size:12px; margin-top:3px; }}
.badge {{ display:inline-block; border:1px solid; border-radius:99px;
  padding:4px 10px; font-size:11px; font-weight:700; letter-spacing:.04em; }}
.vazio {{ color:#74747f; text-align:center; padding:28px !important; }}
</style></head>
<body><div class="wrap">
  <h1>Pedidos</h1>
  <p class="subhead">Quem deu Start ou gerou PIX no nosso bot — nome e @ iguais ao que a Straton mostra.
  <a href="/diario?k={seguro}">Diário</a></p>
  <table>
    <thead><tr>
      <th>Cliente</th><th>Produto</th><th>Valor</th><th>Data</th><th>Status</th>
    </tr></thead>
    <tbody>{tabela}</tbody>
  </table>
</div></body></html>"""
    )


def _login() -> str:
    return """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Pedidos</title></head>
<body style="background:#0c0c12;color:#fff;font-family:sans-serif;padding:40px">
<form><p>Senha do diário</p>
<input name="k" type="password">
<button type="submit">Entrar</button></form>
</body></html>"""
