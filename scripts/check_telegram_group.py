"""Diagnóstico do grupo do Telegram: o bot está lá e consegue ver quem entrou?

Roda antes de ligar qualquer coisa. Só lê, não configura nada.
"""

import sys

import httpx

from app.config import get_settings

sys.stdout.reconfigure(encoding="utf-8")
S = get_settings()


def chamar(metodo, **params):
    if not S.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN não está configurado")
    url = f"https://api.telegram.org/bot{S.telegram_bot_token}/{metodo}"
    with httpx.Client(timeout=20) as client:
        corpo = client.get(url, params=params).json()
    if not corpo.get("ok"):
        return None, corpo.get("description") or "erro desconhecido"
    return corpo.get("result"), None


eu, erro = chamar("getMe")
if erro:
    raise SystemExit(f"getMe falhou: {erro}")
print(f"bot: @{eu.get('username')} (id {eu.get('id')})")
print(f"  pode ser adicionado a grupos: {eu.get('can_join_groups')}")
print(f"  lê todas as mensagens do grupo: {eu.get('can_read_all_group_messages')}")

# Se um webhook já estiver ativo, getUpdates para de funcionar. Precisamos saber.
hook, erro = chamar("getWebhookInfo")
if hook:
    print(f"\nwebhook atual: {hook.get('url') or '<nenhum>'}")
    if hook.get("allowed_updates"):
        print(f"  updates permitidos: {hook['allowed_updates']}")
    if hook.get("last_error_message"):
        print(f"  último erro: {hook['last_error_message']}")

alvo = getattr(S, "telegram_group_chat_id", "") or S.telegram_default_chat_id
if not alvo:
    print("\nNenhum grupo configurado. Procurando nos updates recentes...")
    updates, erro = chamar("getUpdates", limit=100)
    if erro:
        print(f"  getUpdates falhou: {erro}")
        print("  (se houver webhook ativo, isso é esperado)")
    else:
        vistos = {}
        for update in updates or []:
            for chave in ("message", "channel_post", "chat_member", "my_chat_member"):
                chat = (update.get(chave) or {}).get("chat") or {}
                if chat.get("type") in {"group", "supergroup", "channel"}:
                    vistos[chat["id"]] = f"{chat.get('title')} ({chat.get('type')})"
        if vistos:
            print("  grupos/canais encontrados:")
            for chat_id, titulo in vistos.items():
                print(f"    {chat_id}  {titulo}")
        else:
            print("  nenhum grupo apareceu. Adicione o bot ao grupo e mande uma")
            print("  mensagem qualquer lá, depois rode este script de novo.")
    raise SystemExit(0)

print(f"\nconferindo o grupo {alvo}")
chat, erro = chamar("getChat", chat_id=alvo)
if erro:
    raise SystemExit(f"  getChat falhou: {erro}")
print(f"  título: {chat.get('title')}  tipo: {chat.get('type')}")

quantos, erro = chamar("getChatMemberCount", chat_id=alvo)
print(f"  membros: {quantos if not erro else erro}")

# O bot só recebe quem entrou se for administrador. É isso que decide tudo.
comigo, erro = chamar("getChatMember", chat_id=alvo, user_id=eu.get("id"))
if erro:
    print(f"  getChatMember do próprio bot falhou: {erro}")
else:
    status = comigo.get("status")
    print(f"  status do bot no grupo: {status}")
    if status == "administrator":
        print("  OK: como admin, ele recebe os eventos de quem entra e sai.")
    else:
        print("  PROBLEMA: sem ser administrador o bot não recebe chat_member.")
