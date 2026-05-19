from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Captain Taxi Dispatch"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database (component vars — same as core)
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "captaintaxi"
    postgres_user: str = "captaintaxi"
    postgres_password: str = ""

    # Redis (component vars)
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # Assignment
    assignment_timeout_seconds: int = 90
    max_assignment_radius_km: float = 15.0
    nearby_drivers_limit: int = 10

    # Redis TTL for driver-location entries (referenced by redis_client.py).
    # Longer than the typical app GPS ping interval so drivers don't
    # disappear from the geo index between updates.
    driver_location_ttl: int = 300

    # Cities
    supported_cities: list[str] = ["saskatoon", "regina"]

    @property
    def database_url(self) -> str:
        from urllib.parse import quote
        password = quote(self.postgres_password, safe="")
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        from urllib.parse import quote
        password = quote(self.postgres_password, safe="")
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        from urllib.parse import quote
        password = quote(self.redis_password, safe="")
        return f"redis://:{password}@{self.redis_host}:{self.redis_port}/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
