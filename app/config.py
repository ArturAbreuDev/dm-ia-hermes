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
    # Quem recebe o aviso de conversa quente. Vazio cai no chat acima. Sem token
    # ou sem destino o aviso não sai, e isso fica no log em vez de virar erro.
    alerts_enabled: bool = True
    alert_chat_id: str = ""
    # O grupo/canal onde o Botgram joga quem comprou. Estar lá dentro é a prova
    # de pagamento mais confiável que temos sem API de checkout.
    telegram_group_chat_id: str = ""
    # Grupo de prévias (ex.: "livia porevias"). Só postagens do /publicar.
    # Nunca mistura com o chat pessoal nem com o VIP de quem pagou.
    telegram_previews_chat_id: str = ""
    telegram_webhook_secret: str = ""
    # Chave live/test da StratonBot (sb_live_… / sb_test_…). Serve pra listar
    # PIX pendente e avisar antes de expirar.
    straton_api_key: str = ""
    # Segredo do webhook da Straton (HMAC). Se vazio, cai no payment_webhook_secret.
    straton_webhook_secret: str = ""
    # Protege o cron de recuperação de PIX. Vercel Cron manda Authorization: Bearer.
    cron_secret: str = ""
    # API key do cron-job.org (Settings → API). Dispara o RMK a cada 5 min no Hobby.
    cronjobs_api_key: str = ""

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
    max_replies_without_sale: int = 8
    # Depois de já ter mandado o link, insistir não converte.
    max_replies_after_link: int = 3
    # Uma recusa; na segunda ela some.
    freebie_strikes: int = 1
    # Quem insiste que ela é robô não é convencido, é perdido.
    ai_strikes: int = 1
    # Uma recusa vendendo o pack; na segunda ela some.
    live_strikes: int = 1
    # Sala e elogio não entram na conversa. Zero = vácuo na hora.
    small_talk_replies: int = 0

    # Segredo compartilhado com a plataforma de checkout. Sem ele o webhook de
    # pagamento recusa tudo, para ninguém marcar lead como pago de fora.
    payment_webhook_secret: str = ""
    # Nome do parâmetro em que a plataforma aceita uma referência livre, para o
    # IGSID voltar no webhook e a venda saber de quem foi. Kirvano usa "src",
    # AbacatePay usa "externalId". Vazio desliga o rastreio.
    checkout_ref_param: str = ""

    def checkout_provider(self) -> str:
        """Qual checkout está ativo agora: straton ou botgram.

        O /diario pode trocar isso no banco. Sem escolha salva, vale o padrão
        da env (CHECKOUT_DEFAULT), e na falta disso a Straton.
        """
        from app.store import runtime

        escolhido = (runtime.get("checkout_provider") or "").strip().lower()
        if escolhido in {"straton", "botgram"}:
            return escolhido
        padrao = (self.checkout_default or "straton").strip().lower()
        return padrao if padrao in {"straton", "botgram"} else "straton"

    def telegram_vip_bot(self) -> str:
        """Username do bot nosso (funil / Start), sem @."""
        raw = self.telegram_sales_url or "https://t.me/liviagommes_bot"
        parte = raw.rstrip("/").split("/")[-1]
        return parte.lstrip("@") or "liviagommes_bot"

    def chat_dono_privado(self) -> str:
        """Seu Telegram pessoal. Nunca grupo, nunca prévia, nunca VIP."""
        for bruto in (self.telegram_default_chat_id, self.alert_chat_id):
            cid = str(bruto or "").strip()
            if cid and not cid.startswith("-"):
                return cid
        return ""

    def straton_checkout_bot(self) -> str:
        """Bot antigo da Straton (não é mais o CTA)."""
        raw = self.checkout_url_straton or "https://t.me/liviagomesvip_bot"
        parte = raw.rstrip("/").split("/")[-1]
        return parte.lstrip("@").split("?")[0] or "liviagomesvip_bot"

    def active_price_amount(self) -> float:
        limpo = (self.price_straton or "24,90").split("ou")[0]
        limpo = limpo.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        try:
            return float(limpo)
        except ValueError:
            return 24.9

    def active_checkout_url(self) -> str:
        """O link que a IA e o outreach devem mandar agora."""
        if self.checkout_provider() == "botgram":
            return self.checkout_url_botgram or self.checkout_url
        # t.me aberto no Instagram cai na tela genérica (Google/Telegram em inglês).
        # Mandamos nossa página /vip, que abre o app direto.
        if self.base_url:
            return f"{self.base_url}/vip"
        return f"https://t.me/{self.telegram_vip_bot()}"

    def all_checkout_urls(self) -> list[str]:
        """Todos os links conhecidos, para achar e limpar o que já saiu."""
        urls = [
            f"https://t.me/{self.telegram_vip_bot()}",
            self.checkout_url_straton,
            self.checkout_url_botgram,
            self.checkout_url,
        ]
        if self.base_url:
            urls.append(f"{self.base_url}/vip")
        return [u for u in urls if u]

    def active_price(self) -> str:
        if self.checkout_provider() == "botgram":
            return self.price_botgram
        return self.price_straton

    def active_price_spoken(self) -> str:
        if self.checkout_provider() == "botgram":
            return self.price_spoken_botgram
        return self.price_spoken_straton

    def checkout_link(self, igsid: str | None = None) -> str:
        """O link de venda ativo, com a marca do lead quando a plataforma permite."""
        base = self.active_checkout_url()
        if not base or not self.checkout_ref_param or not igsid:
            return base
        # Link de Telegram (t.me/...) não aceita query string do nosso jeito.
        if "t.me/" in base:
            return base
        juncao = "&" if "?" in base else "?"
        return f"{base}{juncao}{self.checkout_ref_param}={igsid}"

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
    # Fallback legado. O ativo vem de active_checkout_url().
    checkout_url: str = ""
    checkout_url_straton: str = "https://t.me/liviagomesvip_bot"
    checkout_url_botgram: str = "https://botgram.club/livia-gomes-fotos"
    checkout_default: str = "straton"
    price_straton: str = "24,90"
    price_spoken_straton: str = "vinte e quatro reais e noventa"
    # Pack pra quem pagou PIX na DM (sem Telegram). URL pública (Blob). Vazio = só avisa você.
    pack_delivery_url: str = ""
    price_botgram: str = "19,90, 29,90 ou 39,90"
    price_spoken_botgram: str = (
        "dezenove e noventa, vinte e nove e noventa ou trinta e nove e noventa"
    )
    # Mantidos por compatibilidade com scripts/testes antigos; preferir active_*.
    price: str = "24,90"
    price_spoken: str = "vinte e quatro reais e noventa"
    # Token do Vercel Blob (free 1 GB). Sem ele, mídia vai pro Neon.
    blob_read_write_token: str = ""
    whatsapp_url: str = ""
    # Linktree: @ do Instagram (sem @), canal de prévias e Privacy.
    instagram_handle: str = ""
    telegram_previews_url: str = ""
    privacy_url: str = ""
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
