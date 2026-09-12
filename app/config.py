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
    transcribe_model: str = "whisper-1"

    telegram_bot_token: str = ""
    telegram_default_chat_id: str = ""
    # O grupo/canal onde o Botgram joga quem comprou. Estar lá dentro é a prova
    # de pagamento mais confiável que temos sem API de checkout.
    telegram_group_chat_id: str = ""
    telegram_webhook_secret: str = ""

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model: str = "eleven_v3"
    elevenlabs_sample_rate: int = 24000
    # O Instagram recusa mp3; pcm vira wav, que ele aceita.
    elevenlabs_output_format: str = "pcm_24000"
    # No v3 a estabilidade só aceita 0.0 (criativo), 0.5 (natural) ou 1.0 (robusto).
    elevenlabs_stability: float = 0.5
    voice_replies_enabled: bool = True
    voice_max_chars: int = 300
    # Áudios prontos que ela manda ao explicar o fluxo ou ao passar o link.
    canned_audio_enabled: bool = True
    voice_director_enabled: bool = True
    voice_director_model: str = ""
    public_base_url: str = ""

    # Depois que a pessoa paga, a conversa se despede em poucas mensagens.
    post_payment_replies: int = 2
    # Conversa que não vira venda tem fim: ela se despede e para de responder.
    max_replies_without_sale: int = 16
    # Depois de já ter mandado o link, insistir não converte.
    max_replies_after_link: int = 6
    # Quantas vezes ela desconversa antes de desistir de quem só quer de graça.
    freebie_strikes: int = 2
    # Quem insiste que ela é robô não é convencido, é perdido.
    ai_strikes: int = 2
    # Quantas vezes ela desconversa sobre gravar/encontrar antes de deixar morrer.
    live_strikes: int = 3
    # Teto de quem só faz sala e só elogia. No dia 11 a conversa mais longa teve
    # 46 mensagens dele e não vendeu nada, e a venda saiu da conversa mais curta:
    # insistir com quem só puxa conversa gasta o dia e não converte.
    small_talk_replies: int = 8

    # Segredo compartilhado com a plataforma de checkout. Sem ele o webhook de
    # pagamento recusa tudo, para ninguém marcar lead como pago de fora.
    payment_webhook_secret: str = ""
    # Nome do parâmetro em que a plataforma aceita uma referência livre, para o
    # IGSID voltar no webhook e a venda saber de quem foi. Kirvano usa "src",
    # AbacatePay usa "externalId". Vazio desliga o rastreio.
    checkout_ref_param: str = ""

    def checkout_link(self, igsid: str | None = None) -> str:
        """O link de venda, com a marca do lead quando a plataforma permite."""
        if not self.checkout_url or not self.checkout_ref_param or not igsid:
            return self.checkout_url
        juncao = "&" if "?" in self.checkout_url else "?"
        return f"{self.checkout_url}{juncao}{self.checkout_ref_param}={igsid}"

    # Quando a Lívia responde na mão, o bot sai de cena por um tempo. A janela
    # reinicia a cada mensagem dela, e volta sozinha quando ela para.
    human_takeover_minutes: int = 15

    reply_delay_enabled: bool = True
    reply_delay_max_seconds: float = 120.0

    story_context_enabled: bool = True
    story_sync_minutes: int = 30
    # A conta que posta os stories do dia a dia pode ser outra, diferente da que
    # recebe as DMs. Se estes campos ficarem vazios, usamos a própria conta do bot.
    stories_instagram_user_id: str = ""
    stories_instagram_access_token: str = ""
    diary_password: str = ""

    @property
    def admin_key(self) -> str:
        """Uma senha só para o /diario e para as rotas de lead."""
        return self.diary_password

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
    def stories_account(self) -> tuple[str, str]:
        """De qual conta ler os stories: a dedicada, se houver, senão a do bot."""
        if self.stories_instagram_user_id and self.stories_instagram_access_token:
            return self.stories_instagram_user_id, self.stories_instagram_access_token
        return self.instagram_id, self.instagram_access_token

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
