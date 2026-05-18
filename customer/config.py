from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Captain Taxi Customer Service"
    debug: bool = False

    # Anthropic
    anthropic_api_key: str

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str = "whatsapp:+13068811542"
    twilio_phone_from: str = "+16393983373"

    # Vapi
    vapi_private_key: str = ""
    vapi_phone_saskatoon: str = "+13062420000"
    vapi_phone_regina: str = "+13067752222"
    vapi_webhook_secret: str = ""

    # Database (component vars)
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "captaintaxi"
    postgres_user: str = "captaintaxi"
    postgres_password: str = ""

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    conversation_ttl_seconds: int = 3600

    # Internal service URLs
    dispatch_agent_url: str = "http://dispatch:8001"
    dispatch_agent_api_key: str = ""
    admin_agent_url: str = "http://admin:8006"

    # Owner & company
    owner_phone: str = "+13068811542"
    amara_phone: str = "+13068500760"
    owner_email: str = "admin@captain.taxi"
    saskatoon_number: str = "+13062420000"
    regina_number: str = "+13067752222"
    company_name: str = "Captain Taxi"

    @property
    def database_url(self) -> str:
        from urllib.parse import quote
        password = quote(self.postgres_password, safe="")
        return f"postgresql+asyncpg://{self.postgres_user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def redis_url(self) -> str:
        from urllib.parse import quote
        password = quote(self.redis_password, safe="")
        return f"redis://:{password}@{self.redis_host}:{self.redis_port}/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
