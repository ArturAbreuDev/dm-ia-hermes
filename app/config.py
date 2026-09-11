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

    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""

    business_name: str = "Hermes"
    business_tone: str = "consultivo, direto e brasileiro"
    checkout_url: str = ""
    whatsapp_url: str = ""
    handoff_keywords: str = "humano,atendente,pessoa"

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
    def handoff_terms(self) -> list[str]:
        return [item.strip().lower() for item in self.handoff_keywords.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
