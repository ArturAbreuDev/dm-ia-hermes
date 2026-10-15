"""Fluxo visual do bot (React Flow): banner, Start com mídia, RMK com horário."""

from __future__ import annotations

import json
from typing import Any

from app.store import runtime

CHAVE = "sales_funnel"
CAMPOS_MIDIA = ("video_url", "photo_url", "video_file_id", "photo_file_id")

START_TEXT = (
    "Seja muito bem-vindo! 😍🔥\n\n"
    "Falta bem pouco para você entrar no meu Canal VIP... 😏\n\n"
    "🌶️ Interação com os assinantes\n"
    "🌶️ Fotos e vídeos exclusivos\n"
    "🔥 Conteúdo novo toda semana\n\n"
    "Já deixei um gostinho do que te espera por lá... 👀💋\n\n"
    "👉 Novos assinantes: clique em /start\n\n"
    "Por apenas R$ 24,90, você pode entrar e passar um tempinho comigo. 😉\n\n"
    "🤫 Pagamento 100% anônimo\n\n"
    "🔥 Escolha seu plano e desbloqueie o acesso aos conteúdos exclusivos."
)

_BANNER_TEXT = (
    "Seja muito bem-vindo! 😍🔥\n"
    "Falta bem pouco para você entrar no meu Canal VIP.\n\n"
    "Toca em Start, escolhe o acesso e cai no grupo na hora."
)
_BANNER_SHORT = "Priv da Lívia — Start, Acesso VIP R$ 24,90, cai no grupo."


def _banner_node() -> dict[str, Any]:
    return {
        "id": "banner",
        "type": "banner",
        "position": {"x": 40, "y": -80},
        "data": {
            "label": "Perfil do bot",
            "name": "Livia Gomes",
            "short": _BANNER_SHORT,
            "text": _BANNER_TEXT,
            "photo_url": "",
        },
    }


def default_funnel() -> dict[str, Any]:
    return {
        "version": 3,
        "nodes": [
            _banner_node(),
            {
                "id": "start",
                "type": "start",
                "position": {"x": 40, "y": 420},
                "data": {
                    "label": "Start + vídeo",
                    "text": START_TEXT,
                    "video_url": "",
                    "photo_url": "",
                },
            },
            {
                "id": "pix",
                "type": "pix",
                "position": {"x": 420, "y": 80},
                "data": {"label": "Acesso VIP (PIX)"},
            },
            {
                "id": "card",
                "type": "card",
                "position": {"x": 420, "y": 220},
                "data": {"label": "Cartão"},
            },
            {
                "id": "paid",
                "type": "paid",
                "position": {"x": 700, "y": 150},
                "data": {"label": "Pagou → grupo"},
            },
            {
                "id": "r1",
                "type": "rmk",
                "position": {"x": 40, "y": 780},
                "data": {
                    "label": "RMK 1",
                    "delay_minutes": 15,
                    "text": (
                        "Falta bem pouco pra você entrar no Canal VIP 😏\n"
                        "O gostinho já foi. Agora é só liberar o acesso."
                    ),
                    "video_url": "",
                    "photo_url": "",
                },
            },
            {
                "id": "r2",
                "type": "rmk",
                "position": {"x": 340, "y": 520},
                "data": {
                    "label": "RMK 2",
                    "delay_minutes": 180,
                    "text": (
                        "Ainda tô com sua vaga.\n"
                        "Por R$ 24,90 você entra e passa um tempinho comigo. "
                        "Pagamento 100% anônimo."
                    ),
                    "video_url": "",
                    "photo_url": "",
                },
            },
            {
                "id": "r3",
                "type": "rmk",
                "position": {"x": 640, "y": 520},
                "data": {
                    "label": "RMK 3",
                    "delay_minutes": 1440,
                    "text": (
                        "Ainda dá tempo de entrar.\n"
                        "Escolhe o plano e desbloqueia o acesso aos conteúdos exclusivos."
                    ),
                    "loop": True,
                    "loop_minutes": 1440,
                    "video_url": "",
                    "photo_url": "",
                },
            },
        ],
        "edges": [
            {"id": "e-banner-start", "source": "banner", "target": "start"},
            {"id": "e-start-pix", "source": "start", "target": "pix"},
            {"id": "e-start-card", "source": "start", "target": "card"},
            {"id": "e-start-r1", "source": "start", "target": "r1"},
            {"id": "e-r1-r2", "source": "r1", "target": "r2"},
            {"id": "e-r2-r3", "source": "r2", "target": "r3"},
            {"id": "e-pix-paid", "source": "pix", "target": "paid"},
            {"id": "e-card-paid", "source": "card", "target": "paid"},
        ],
    }


def _texto_start_antigo(texto: str) -> bool:
    t = (texto or "").strip().lower()
    return (not t) or t.startswith("aqui é o meu priv") or t.startswith("oi amor")


def _migrar(dados: dict[str, Any]) -> dict[str, Any]:
    if int(dados.get("version") or 0) >= 3:
        return dados
    novo = default_funnel()
    velho = {str(n.get("id")): n for n in dados.get("nodes") or [] if n.get("id")}
    start_velho = ""
    for n in dados.get("nodes") or []:
        if n.get("type") == "start":
            start_velho = str((n.get("data") or {}).get("text") or "")
            break
    if not _texto_start_antigo(start_velho) and start_velho:
        return ensure_defaults(dados)
    for n in novo["nodes"]:
        antigo = velho.get(str(n["id"]))
        if not antigo:
            continue
        data = dict(n.get("data") or {})
        old_data = antigo.get("data") or {}
        for chave in ("video_url", "photo_url"):
            if old_data.get(chave):
                data[chave] = old_data[chave]
        n["data"] = data
    return novo


def ensure_defaults(dados: dict[str, Any]) -> dict[str, Any]:
    nodes = list(dados.get("nodes") or [])
    edges = list(dados.get("edges") or [])
    if not any((n.get("type") or "") == "banner" for n in nodes):
        nodes.insert(0, _banner_node())
        tem_start = any((n.get("type") or "") == "start" for n in nodes)
        start_id = next(
            (str(n.get("id")) for n in nodes if n.get("type") == "start"),
            "start",
        )
        if tem_start and not any(
            str(e.get("source")) == "banner" and str(e.get("target")) == start_id
            for e in edges
        ):
            edges.insert(
                0,
                {"id": "e-banner-start", "source": "banner", "target": start_id},
            )
    return {"version": int(dados.get("version") or 3), "nodes": nodes, "edges": edges}


def _nodes_limpos(nodes: list) -> list[dict[str, Any]]:
    limpos: list[dict[str, Any]] = []
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        pos = n.get("position") or {}
        limpos.append(
            {
                "id": str(n.get("id")),
                "type": n.get("type") or "default",
                "position": {
                    "x": float(pos.get("x") or 0),
                    "y": float(pos.get("y") or 0),
                },
                "data": n.get("data") if isinstance(n.get("data"), dict) else {},
            }
        )
    return limpos


def load() -> dict[str, Any]:
    bruto = runtime.get(CHAVE)
    if not bruto:
        return default_funnel()
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError:
        return default_funnel()
    if not isinstance(dados, dict) or not dados.get("nodes"):
        return default_funnel()
    return ensure_defaults(_migrar(dados))


def _preservar_midia(nodes: list[dict[str, Any]], anterior: dict[str, Any]) -> None:
    prev = {
        str(n.get("id")): n
        for n in (anterior.get("nodes") or [])
        if isinstance(n, dict) and n.get("id")
    }
    for n in nodes:
        old = (prev.get(str(n.get("id"))) or {}).get("data") or {}
        data = n.setdefault("data", {})
        if not isinstance(data, dict):
            n["data"] = {}
            data = n["data"]
        for chave in CAMPOS_MIDIA:
            if not str(data.get(chave) or "").strip() and old.get(chave):
                data[chave] = old[chave]


def save(dados: dict[str, Any], *, preservar_midia: bool = True) -> dict[str, Any]:
    nodes = _nodes_limpos(dados.get("nodes") or [])
    edges = dados.get("edges") or []
    if not isinstance(edges, list):
        raise ValueError("fluxo inválido")
    if preservar_midia:
        bruto = runtime.get(CHAVE)
        anterior: dict[str, Any] = {}
        if bruto:
            try:
                parsed = json.loads(bruto)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                anterior = parsed
        _preservar_midia(nodes, anterior)
    limpo = ensure_defaults({"version": 3, "nodes": nodes, "edges": edges})
    runtime.set(CHAVE, json.dumps(limpo, ensure_ascii=False))
    return limpo


def anexar_midia(node_id: str, campo: str, url: str) -> dict[str, Any]:
    if campo not in CAMPOS_MIDIA:
        raise ValueError("campo inválido")
    dados = load()
    achou = False
    for n in dados.get("nodes") or []:
        if str(n.get("id")) == str(node_id):
            data = n.setdefault("data", {})
            data[campo] = url
            if campo == "video_url" and not url:
                data["video_file_id"] = ""
            if campo == "photo_url" and not url:
                data["photo_file_id"] = ""
            achou = True
            break
    if not achou:
        raise ValueError("bloco não encontrado")
    return save(dados, preservar_midia=False)


def _node_map(funil: dict[str, Any]) -> dict[str, dict]:
    return {str(n.get("id")): n for n in funil.get("nodes") or [] if n.get("id")}


def _saidas(funil: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for e in funil.get("edges") or []:
        src, dst = str(e.get("source") or ""), str(e.get("target") or "")
        if src and dst:
            out.setdefault(src, []).append(dst)
    return out


def _por_tipo(funil: dict[str, Any], tipo: str) -> dict[str, Any] | None:
    for n in funil.get("nodes") or []:
        if (n.get("type") or "") == tipo:
            return n
    return None


def banner() -> dict[str, str]:
    n = _por_tipo(load(), "banner") or {}
    data = n.get("data") or {}
    return {
        "name": str(data.get("name") or "").strip(),
        "short": str(data.get("short") or "").strip(),
        "text": str(data.get("text") or "").strip(),
        "photo_url": str(data.get("photo_url") or "").strip(),
    }


def start_payload() -> dict[str, str]:
    n = _por_tipo(load(), "start") or {}
    data = n.get("data") or {}
    return {
        "id": str(n.get("id") or "start"),
        "text": str(data.get("text") or "").strip(),
        "video_url": str(data.get("video_url") or "").strip(),
        "photo_url": str(data.get("photo_url") or "").strip(),
        "video_file_id": str(data.get("video_file_id") or "").strip(),
        "photo_file_id": str(data.get("photo_file_id") or "").strip(),
    }


def start_text() -> str:
    return start_payload()["text"]


def start_video_url() -> str:
    return start_payload()["video_url"]


def rmk_steps() -> list[dict[str, Any]]:
    """Cadeia Start → (espera) → rmk, usando delay_minutes de cada RMK."""
    funil = load()
    nos = _node_map(funil)
    saidas = _saidas(funil)
    passos: list[dict[str, Any]] = []
    starts = [str(n.get("id")) for n in funil.get("nodes") or [] if n.get("type") == "start"]
    atuais: list[str] = []
    for sid in starts or ["start"]:
        atuais.extend(saidas.get(sid) or [])
    vistos: set[str] = set()
    minutos = 15
    while atuais:
        nxt = atuais.pop(0)
        if nxt in vistos:
            continue
        vistos.add(nxt)
        node = nos.get(nxt) or {}
        tipo = node.get("type") or ""
        data = node.get("data") or {}
        if tipo in {"pix", "card", "paid", "banner", "start"}:
            continue
        if tipo == "wait":
            try:
                minutos = max(1, int(data.get("minutes") or 15))
            except (TypeError, ValueError):
                minutos = 15
            atuais.extend(saidas.get(nxt) or [])
            continue
        if tipo == "rmk":
            try:
                delay = int(data.get("delay_minutes") or minutos)
            except (TypeError, ValueError):
                delay = minutos
            loop = data.get("loop")
            try:
                loop_min = int(data.get("loop_minutes") or 1440)
            except (TypeError, ValueError):
                loop_min = 1440
            passos.append(
                {
                    "id": nxt,
                    "minutes": max(1, delay),
                    "loop": False if loop is False else True,
                    "loop_minutes": max(5, loop_min),
                    "text": str(data.get("text") or "").strip(),
                    "video_url": str(data.get("video_url") or "").strip(),
                    "photo_url": str(data.get("photo_url") or "").strip(),
                    "video_file_id": str(data.get("video_file_id") or "").strip(),
                    "photo_file_id": str(data.get("photo_file_id") or "").strip(),
                }
            )
            atuais.extend(saidas.get(nxt) or [])
            minutos = 180
    return passos


def midias_previa() -> list[dict[str, Any]]:
    """Start + RMKs que têm foto/vídeo — o que vai pro grupo de prévias."""
    itens: list[dict[str, Any]] = []
    start = start_payload()
    itens.append(
        {
            "id": start.get("id") or "start",
            "text": start.get("text") or "",
            "video_url": start.get("video_url") or "",
            "photo_url": start.get("photo_url") or "",
            "video_file_id": start.get("video_file_id") or "",
            "photo_file_id": start.get("photo_file_id") or "",
        }
    )
    itens.extend(rmk_steps())
    out: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in itens:
        chave = (
            str(item.get("video_file_id") or "")
            or str(item.get("photo_file_id") or "")
            or str(item.get("video_url") or "")
            or str(item.get("photo_url") or "")
        )
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        out.append(item)
    return out


def rmk_gaps_hours() -> tuple[float, ...]:
    passos = rmk_steps()
    if not passos:
        return (0.25, 3.0, 24.0)
    return tuple(max(0.05, p["minutes"] / 60.0) for p in passos)
