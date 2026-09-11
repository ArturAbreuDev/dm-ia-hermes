# Hermes — DMs de venda no Instagram

API FastAPI com spec OpenAPI para receber webhooks da Instagram Messaging API, gerar uma resposta com intenção de venda (OpenAI) e responder o Direct.

O Instagram **não permite disparo frio**. O bot só responde quem já escreveu, dentro da janela de 24 horas.

## O que entra no ar

| Rota | Função |
|------|--------|
| `GET /api/instagram/webhook` | Verificação do webhook da Meta |
| `POST /api/instagram/webhook` | Recebe a DM, gera resposta e envia |
| `GET /webhooks/instagram` | Alias do webhook |
| `GET /v1/health` | Saúde da API |
| `POST /v1/simulate` | Testa o vendedor sem Instagram |
| `POST /v1/messages` | Envia um DM manual no Instagram |
| `POST /v1/telegram/messages` | Envia texto pelo bot do Telegram |
| `POST /v1/telegram/voice` | Envia áudio como *voice message* (OGG/Opus) |
| `GET /docs` | Swagger UI |
| `GET /openapi.json` | Spec OpenAPI |

## 1. Configurar o webhook da Meta

Callback URL:

`https://SEU-DOMINIO.vercel.app/api/instagram/webhook`

Verify Token: o valor de `WEBHOOK_VERIFY_TOKEN` (no `.env` e nas env vars da Vercel).

No App Dashboard da Meta:

1. Instagram Professional (Business ou Creator).
2. Produto **Instagram** / Messaging, campo de webhook `messages`.
3. Cole a Callback URL e o Verify Token.
4. A Meta faz um GET com `hub.mode=subscribe`, `hub.verify_token` e `hub.challenge`.
5. O Hermes devolve o `hub.challenge` em texto puro se o token bater.

Env obrigatórias:

- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_USER_ID`
- `WEBHOOK_VERIFY_TOKEN`

Opcional depois: `META_APP_SECRET` para validar `X-Hub-Signature-256`.

## 2. Subir o Hermes

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite o `.env`:

- `WEBHOOK_VERIFY_TOKEN` para a Meta verificar o GET
- `INSTAGRAM_USER_ID` da conta Professional
- `INSTAGRAM_ACCESS_TOKEN` (token IG)
- `OPENAI_API_KEY` para as respostas de venda
- `TELEGRAM_BOT_TOKEN` do BotFather
- `TELEGRAM_DEFAULT_CHAT_ID` depois do primeiro `/start` no bot
- `CHECKOUT_URL` e `WHATSAPP_URL` para o fechamento
- produtos em `data/catalog.yaml`
- tom e objeções em `data/playbook.yaml`

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Abra `http://localhost:8000/docs`.

## 3. Testar o vendedor

```bash
curl -X POST http://localhost:8000/v1/simulate ^
  -H "Content-Type: application/json" ^
  -d "{\"sender_id\":\"demo\",\"text\":\"Quanto custa a mentoria?\"}"
```

Sem `OPENAI_API_KEY`, o Hermes usa um fallback com preço do catálogo.

O Telegram só entrega mensagem para quem já abriu o bot e tocou em **Start**. Voice message exige OGG com codec Opus (`ffmpeg -i audio.mp3 -c:a libopus -b:a 64k audio.ogg`).

## Políticas que o bot já respeita

- Só responde mensagem inbound (não inicia conversa)
- Ignora ecos da própria conta (`is_echo`)
- Evita responder o mesmo `mid` duas vezes
- Encaminha para humano se a pessoa pedir atendente
- Não inventa produto ou preço fora do catálogo
