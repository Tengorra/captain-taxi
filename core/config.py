from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database - Railway provides DATABASE_URL directly
    DATABASE_URL: str = ""
    REDIS_URL: str = ""

    # Fallback individual fields (for local dev)
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "captaintaxi"
    postgres_user: str = "captaintaxi"
    postgres_password: str = ""

    # Redis fallback (for local dev)
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""

    # Anthropic
    anthropic_api_key: str

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    # Owner contacts — hardcoded fallbacks, overrideable via env
    owner_phone: str = "+13068811542"
    amara_phone: str = "+13068500760"
    owner_email: str = "owner@captaintaxi.ca"

    # Company
    company_name: str = "Captain Taxi"
    saskatoon_phone: str = "306-242-0000"
    regina_phone: str = "306-775-2222"

    # App
    secret_key: str = "change-me"
    environment: str = "production"
    log_level: str = "INFO"
    digest_hour: int = 8
    digest_minute: int = 0

    # QuickBooks
    qb_client_id: str = ""
    qb_client_secret: str = ""
    qb_refresh_token: str = ""
    qb_realm_id: str = ""

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            # Railway gives postgresql://, asyncpg needs postgresql+asyncpg://
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        from urllib.parse import quote
        password = quote(self.postgres_password, safe="")
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return url
        from urllib.parse import quote
        password = quote(self.postgres_password, safe="")
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        from urllib.parse import quote
        password = quote(self.redis_password, safe="")
        return f"redis://:{password}@{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()