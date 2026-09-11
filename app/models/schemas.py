from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "dm-ia-hermes"


class SimulateRequest(BaseModel):
    sender_id: str = Field(min_length=1, examples=["igsid_demo"])
    text: str = Field(min_length=1, examples=["Quanto custa o plano Pro?"])


class SimulateResponse(BaseModel):
    reply: str
    handoff: bool = False
    intent: str | None = None


class SendMessageRequest(BaseModel):
    recipient_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=1000)


class SendMessageResponse(BaseModel):
    recipient_id: str
    message_id: str | None = None


class TelegramTextRequest(BaseModel):
    chat_id: str | None = Field(default=None, examples=["123456789"])
    to: str | None = Field(default=None, examples=["Artur"])
    text: str = Field(min_length=1, max_length=4096)


class TelegramVoiceRequest(BaseModel):
    chat_id: str | None = Field(default=None, examples=["123456789"])
    to: str | None = Field(default=None, examples=["Artur"])
    audio_path: str = Field(min_length=1)
    caption: str | None = None


class TelegramSendResponse(BaseModel):
    chat_id: str
    message_id: int | None = None
