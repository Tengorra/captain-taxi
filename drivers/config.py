from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # Database (component vars)
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "captaintaxi"
    postgres_user: str = "captaintaxi"
    postgres_password: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_from: str = "+16393983373"

    # SendGrid / SMTP
    sendgrid_api_key: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: str = "dispatch@captain.taxi"
    from_name: str = "Captain Taxi"

    # App
    owner_email: str = "admin@captain.taxi"
    owner_phone: str = "+13068811542"
    amara_phone: str = "+13068500760"
    owner_name: str = "Captain Taxi Owner"
    base_url: str = "https://captain.taxi"
    secret_key: str = "change-me-in-production"

    # Coverage requirements
    min_drivers_saskatoon_day: int = 4
    min_drivers_saskatoon_night: int = 2
    min_drivers_regina_day: int = 3
    min_drivers_regina_night: int = 2

    # Performance thresholds
    cancellation_rate_threshold: float = 0.10
    rating_threshold: float = 4.0
    complaint_threshold_days: int = 30
    complaint_threshold_count: int = 3

    @property
    def database_url(self) -> str:
        from urllib.parse import quote
        password = quote(self.postgres_password, safe="")
        return f"postgresql+asyncpg://{self.postgres_user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
