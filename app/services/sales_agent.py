from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from openai import OpenAI

from app.config import get_settings
from app.store import memory

logger = logging.getLogger(__name__)


@dataclass
class SalesResult:
    reply: str
    intent: str | None = None
    handoff: bool = False
    lead: dict[str, Any] = field(default_factory=dict)


def wants_human(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in get_settings().handoff_terms)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def generate_sales_reply(sender_id: str, user_text: str) -> SalesResult:
    settings = get_settings()
    catalog = _load_yaml(settings.catalog_path)
    playbook = _load_yaml(settings.playbook_path)
    history = memory.get_history(sender_id)

    if not settings.openai_api_key:
        return SalesResult(
            reply=_fallback_reply(user_text, catalog),
            intent="fallback",
        )

    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    system = _system_prompt(settings.business_name, settings.business_tone, catalog, playbook, settings)
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for item in history:
        role = "assistant" if item["role"] == "assistant" else "user"
        messages.append({"role": role, "content": item["text"]})
    if not history or history[-1]["text"] != user_text:
        messages.append({"role": "user", "content": user_text})

    completion = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=messages,
    )
    raw = completion.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Resposta da IA não era JSON: %s", raw)
        return SalesResult(reply=raw[:1000], intent="unparsed")

    reply = str(data.get("reply") or "").strip() or _fallback_reply(user_text, catalog)
    return SalesResult(
        reply=reply[:1000],
        intent=data.get("intent"),
        handoff=bool(data.get("handoff")),
        lead=data.get("lead") or {},
    )


def _system_prompt(business: str, tone: str, catalog: dict, playbook: dict, settings) -> str:
    return f"""
Você é o vendedor consultivo do Instagram Direct da {business}.
Tom: {tone}.
Objetivo: responder DMs com intenção de vender, sem parecer spam.

Regras:
- Só venda o que estiver no catálogo. Nunca invente preço, prazo ou estoque.
- Faça no máximo 1 pergunta de qualificação por mensagem.
- Mensagens curtas (máx. 3 frases), em português do Brasil.
- Se o lead pedir humano, defina handoff=true e seja educado.
- Sempre tente um próximo passo: responder dúvida, oferecer produto certo ou CTA.
- CTA preferencial: checkout {settings.checkout_url or "(não configurado)"} ou WhatsApp {settings.whatsapp_url or "(não configurado)"}.
- Respeite a janela de 24h: o usuário já escreveu, então responda como RESPONSE.

Catálogo JSON:
{json.dumps(catalog, ensure_ascii=False)}

Playbook JSON:
{json.dumps(playbook, ensure_ascii=False)}

Responda APENAS um JSON com este formato:
{{
  "intent": "saudacao|preco|produto|objecao|checkout|suporte|handoff|outro",
  "handoff": false,
  "lead": {{"interesse": "", "orcamento": "", "prazo": ""}},
  "reply": "texto que será enviado no Instagram"
}}
""".strip()


def _match_product(user_text: str, products: list[dict[str, Any]]) -> dict[str, Any] | None:
    lowered = user_text.lower()
    for product in products:
        name = (product.get("name") or "").lower()
        product_id = (product.get("id") or "").replace("-", " ")
        if name and name in lowered:
            return product
        if product_id and product_id in lowered:
            return product
        for token in name.split():
            if len(token) > 4 and token in lowered:
                return product
    return None


def _fallback_reply(user_text: str, catalog: dict) -> str:
    products = catalog.get("products") or []
    names = ", ".join(item.get("name", "") for item in products[:3] if item.get("name"))
    lowered = user_text.lower()
    asking_price = any(word in lowered for word in ("preço", "preco", "valor", "custa", "quanto"))
    matched = _match_product(user_text, products)
    if matched and asking_price:
        return (
            f"{matched.get('name')} fica {matched.get('price')}. "
            f"{matched.get('summary', '')} Quer que eu te envie o link para fechar?"
        )
    if asking_price and products:
        first = products[0]
        return (
            f"{first.get('name')} fica {first.get('price')}. "
            "Quer que eu te explique o que está incluso?"
        )
    if names:
        return f"Posso te ajudar a escolher. Hoje temos {names}. O que você está procurando?"
    return "Recebi sua mensagem. Me conta o que você procura que eu te indico a melhor opção."
