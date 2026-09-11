from functools import lru_cache
from pathlib import Path
import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "development"

    meta_app_secret: str = ""
    meta_verify_token: str = ""
    webhook_verify_token: str = ""

    instagram_page_id: str = ""
    instagram_user_id: str = ""
    instagram_access_token: str = ""
    graph_api_version: str = "v21.0"
    graph_api_base_url: str = "https://graph.instagram.com"

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_temperature: float = 0.9

    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_multilingual_v2"
    elevenlabs_sample_rate: int = 24000
    elevenlabs_output_format: str = "mp3_44100_128"
    voice_replies_enabled: bool = True
    voice_max_chars: int = 300
    public_base_url: str = ""

    business_name: str = "Livia Gomes"
    business_tone: str = "feminina, confiante, provocante de maneira sutil"
    checkout_url: str = ""
    whatsapp_url: str = ""
    telegram_sales_url: str = ""
    handoff_keywords: str = ""
    history_limit: int = 30

    catalog_path: Path = ROOT_DIR / "data" / "catalog.yaml"
    playbook_path: Path = ROOT_DIR / "data" / "playbook.yaml"
    database_path: Path = ROOT_DIR / "data" / "hermes.db"

    @model_validator(mode="after")
    def use_tmp_db_on_vercel(self):
        if os.getenv("VERCEL"):
            self.database_path = Path("/tmp/hermes.db")
        return self

    @property
    def verify_token(self) -> str:
        return self.webhook_verify_token or self.meta_verify_token

    @property
    def instagram_id(self) -> str:
        return self.instagram_user_id or self.instagram_page_id

    @property
    def graph_messages_url(self) -> str:
        return (
            f"{self.graph_api_base_url.rstrip('/')}/"
            f"{self.graph_api_version}/{self.instagram_id}/messages"
        )

    @property
    def base_url(self) -> str:
        if self.public_base_url:
            return self.public_base_url.rstrip("/")
        host = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL")
        return f"https://{host}" if host else ""

    @property
    def voice_ready(self) -> bool:
        return bool(
            self.voice_replies_enabled
            and self.elevenlabs_api_key
            and self.elevenlabs_voice_id
            and self.base_url
        )

    @property
    def handoff_terms(self) -> list[str]:
        return [item.strip().lower() for item in self.handoff_keywords.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
