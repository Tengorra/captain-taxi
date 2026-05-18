from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Captain Taxi BOT"
    debug: bool = False

    # ── ElevenLabs Conversational AI ──────────────────────────────────────────
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    elevenlabs_webhook_secret: str = ""

    # ── Twilio (carries the inbound PSTN leg + warm transfer) ─────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_from: str = "+16393983373"
    # Live human dispatcher numbers — calls transfer here when the bot escalates.
    human_dispatcher_saskatoon: str = "+13062420000"
    human_dispatcher_regina: str = "+13067752222"

    # ── Redis (live log fanout) ───────────────────────────────────────────────
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    log_channel: str = "bot:call_logs"
    log_ttl_seconds: int = 3600

    # ── Internal services ─────────────────────────────────────────────────────
    dispatch_agent_url: str = "http://dispatch:8001"
    dispatch_agent_api_key: str = ""
    orchestrator_url: str = "http://orchestrator:8000"

    # ── Company ───────────────────────────────────────────────────────────────
    company_name: str = "Captain Taxi"
    saskatoon_number: str = "+13062420000"
    regina_number: str = "+13067752222"

    # ── Escalation heuristics ─────────────────────────────────────────────────
    # Number of consecutive tool failures before the bot warm-transfers.
    transfer_after_tool_failures: int = 2
    # Phrases (case-insensitive) that auto-trigger a transfer to a human.
    transfer_trigger_phrases: list[str] = [
        "speak to a human",
        "real person",
        "talk to a person",
        "manager",
        "this is ridiculous",
        "complaint",
        "supervisor",
    ]

    @property
    def redis_url(self) -> str:
        from urllib.parse import quote
        pw = quote(self.redis_password, safe="")
        return f"redis://:{pw}@{self.redis_host}:{self.redis_port}/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
