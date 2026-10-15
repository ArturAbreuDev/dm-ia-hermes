from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.cron import router as cron_router
from app.api.diary import router as diary_router
from app.api.pedidos import router as pedidos_router
from app.api.funnel import router as funnel_router
from app.api.landing import router as landing_router
from app.api.legal import router as legal_router
from app.api.media import router as media_router
from app.api.outreach import router as outreach_router
from app.api.payments import router as payments_router
from app.api.publish import router as publish_router
from app.api.report import router as report_router
from app.api.studio import router as studio_router
from app.api.telegram_hook import router as telegram_hook_router
from app.api.webhook import router as webhook_router

app = FastAPI(
    title="Hermes — Instagram e Telegram Sales API",
    description=(
        "Webhook da Instagram Messaging API, envio de texto e voice no Telegram, "
        "e agente de vendas com OpenAI. Spec em /openapi.json e docs em /docs."
    ),
    version="0.1.0",
    contact={"name": "Hermes"},
)

app.include_router(webhook_router, prefix="/api/instagram/webhook")
app.include_router(webhook_router, prefix="/webhooks/instagram")
app.include_router(admin_router, prefix="/v1")
app.include_router(payments_router, prefix="/v1")
app.include_router(publish_router, prefix="/v1")
app.include_router(cron_router)
app.include_router(telegram_hook_router)
app.include_router(outreach_router)
app.include_router(report_router)
app.include_router(legal_router)
app.include_router(funnel_router)
app.include_router(landing_router)
app.include_router(media_router)
app.include_router(diary_router)
app.include_router(pedidos_router)
app.include_router(studio_router)
