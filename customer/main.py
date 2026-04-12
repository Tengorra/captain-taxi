"""
Captain Taxi — Customer Service Agent
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from config import get_settings
from db.database import init_db
from routers import twilio, vapi, chat, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.getLogger(__name__).info("Starting Captain Taxi Customer Service Agent")
    await init_db()
    yield
    # Shutdown
    logging.getLogger(__name__).info("Shutting down")


app = FastAPI(
    title="Captain Taxi — Customer Service Agent",
    description="AI-powered customer service: phone (Vapi), WhatsApp, SMS, web chat.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

# ── CORS (web chat widget needs this) ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Restrict to your domain in production
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(twilio.router)
app.include_router(vapi.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    return {
        "service": "Captain Taxi Customer Service Agent",
        "status": "running",
        "channels": ["phone", "sms", "whatsapp", "web_chat"],
    }
