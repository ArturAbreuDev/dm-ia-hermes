"""Liga o webhook do Telegram depois que o bot virar admin do grupo.

Roda uma vez. Sem isso, chat_member não chega: a doc é explícita que o tipo
precisa estar em allowed_updates e que o bot precisa ser administrador.
"""

import secrets
import sys

from app.config import get_settings
from app.services import telegram

sys.stdout.reconfigure(encoding="utf-8")
S = get_settings()

if not S.base_url:
    raise SystemExit("PUBLIC_BASE_URL/BASE_URL precisa estar configurado")

segredo = S.telegram_webhook_secret
if not segredo:
    segredo = secrets.token_urlsafe(24).replace("-", "_")
    print("TELEGRAM_WEBHOOK_SECRET não estava configurado. Gerei este:")
    print(f"\n  {segredo}\n")
    print("Coloque no .env e no Vercel ANTES de continuar, senão o webhook")
    print("vai recusar tudo que chegar. Depois rode este script de novo.")
    raise SystemExit(1)

url = f"{S.base_url.rstrip('/')}/webhooks/telegram"
print(f"apontando o Telegram para {url}")
resultado = telegram.set_webhook(url, segredo)
print(f"  setWebhook: {resultado}")

atual = telegram.get_webhook_info()
print(f"\nurl ativa: {atual.get('url')}")
print(f"updates permitidos: {atual.get('allowed_updates')}")
print(f"pendentes: {atual.get('pending_update_count')}")
if atual.get("last_error_message"):
    print(f"último erro: {atual['last_error_message']}")

print("\nAtenção: com webhook ativo o getUpdates para de funcionar (409).")
print("O /v1/telegram/messages com 'to=' depende dele, então prefira chat_id.")
