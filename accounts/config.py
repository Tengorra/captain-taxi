from pydantic_settings import BaseSettings
from functools import lru_cache
from decimal import Decimal


class Settings(BaseSettings):
    # Database (component vars)
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "captaintaxi"
    postgres_user: str = "captaintaxi"
    postgres_password: str = ""

    # QuickBooks
    qb_client_id: str = ""
    qb_client_secret: str = ""
    qb_redirect_uri: str = "http://82.29.178.157/api/accounts/qb/callback"
    qb_environment: str = "production"
    qb_realm_id: str = "9130347323392316"
    qb_refresh_token: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_from: str = "+16393983373"

    # SendGrid
    sendgrid_api_key: str = ""
    email_from: str = "accounts@captain.taxi"
    email_from_name: str = "Captain Taxi Accounts"

    # Business
    driver_commission_rate: Decimal = Decimal("0.75")
    company_gst_number: str = "123456789RT0001"
    owner_email: str = "admin@captain.taxi"
    owner_phone: str = "+13068811542"
    amara_phone: str = "+13068500760"

    # App
    secret_key: str = "change-me"
    log_level: str = "INFO"

    # Reporting
    invoice_reminder_days: int = 14
    invoice_escalation_days: int = 30
    revenue_alert_threshold: float = 0.20

    @property
    def database_url(self) -> str:
        from urllib.parse import quote
        password = quote(self.postgres_password, safe="")
        return f"postgresql+asyncpg://{self.postgres_user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def database_url_sync(self) -> str:
        from urllib.parse import quote
        password = quote(self.postgres_password, safe="")
        return f"postgresql+psycopg2://{self.postgres_user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
