from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .models import Base
import redis
import os
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv()

# Build DB URL from component env vars (same pattern as other agents)
_pg_user = os.getenv("POSTGRES_USER", "captaintaxi")
_pg_password = quote(os.getenv("POSTGRES_PASSWORD", ""), safe="")
_pg_host = os.getenv("POSTGRES_HOST", "db")
_pg_port = os.getenv("POSTGRES_PORT", "5432")
_pg_db = os.getenv("POSTGRES_DB", "captaintaxi")
DATABASE_URL = f"postgresql://{_pg_user}:{_pg_password}@{_pg_host}:{_pg_port}/{_pg_db}"

_redis_password = quote(os.getenv("REDIS_PASSWORD", ""), safe="")
_redis_host = os.getenv("REDIS_HOST", "redis")
_redis_port = os.getenv("REDIS_PORT", "6379")
REDIS_URL = f"redis://:{_redis_password}@{_redis_host}:{_redis_port}/0"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import logging
    log = logging.getLogger(__name__)

    # Only create admin-owned tables that don't exist in shared schema
    admin_tables = {
        "alerts", "driver_earnings", "settings", "announcements",
        # iCabbi MANAGE-tab modules
        "addresses", "areas", "custom_field_defs", "custom_field_values",
        "favourites", "items", "partners",
        # iCabbi ADMIN-tab modules
        "blacklist_entries", "receipts", "owner_statements", "staff",
    }
    for table in Base.metadata.sorted_tables:
        if table.name not in admin_tables:
            continue
        try:
            with engine.begin() as conn:
                table.create(bind=conn, checkfirst=True)
        except Exception as e:
            log.warning("Could not create table %s: %s", table.name, e)

    # Add admin-managed columns to shared tables (safe, idempotent)
    _add_admin_columns()
    _seed_default_settings()


def _add_admin_columns():
    """Add admin-specific columns to existing shared tables if they don't exist."""
    import logging
    log = logging.getLogger(__name__)
    stmts = [
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS performance_score FLOAT DEFAULT 100.0",
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS commission_rate FLOAT DEFAULT 0.30",
    ]
    for stmt in stmts:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception as e:
            log.warning("Column migration: %s", e)


def _seed_default_settings():
    db = SessionLocal()
    try:
        from .models import Settings
        defaults = [
            ("commission_rate_saskatoon", "0.30", "Driver commission rate for Saskatoon (30%)"),
            ("commission_rate_regina", "0.30", "Driver commission rate for Regina (30%)"),
            ("escalation_timeout_hours", "4", "Hours before escalation expires without response"),
            ("digest_hour", "7", "Hour (24h) to send daily digest (local time)"),
            ("low_driver_threshold", "3", "Alert when fewer than N drivers online per city"),
            ("owner_alerts_enabled", "true", "Send WhatsApp alerts to owner"),
            ("amara_alerts_enabled", "true", "Send WhatsApp alerts to Amara"),
            ("weekly_report_day", "monday", "Day to send weekly email report"),
        ]
        for key, value, desc in defaults:
            existing = db.query(Settings).filter_by(key=key).first()
            if not existing:
                db.add(Settings(key=key, value=value, description=desc))
        db.commit()
    finally:
        db.close()
