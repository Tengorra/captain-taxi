"""
Captain Taxi — BOT (voice dispatcher) service.

Runs an ElevenLabs Conversational AI agent that answers the taxi line,
takes the booking, hands it off to the Dispatch service, and warm-transfers
to a human dispatcher when the bot detects trouble (tool failures, abuse,
explicit "speak to a human").

Live call logs are broadcast over a WebSocket so the dashboard can show
each call as it happens.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import health, elevenlabs, calls, logs as logs_router
from services.log_stream import log_broker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("Starting Captain Taxi BOT service")
    await log_broker.start()
    yield
    await log_broker.stop()
    logging.getLogger(__name__).info("BOT service stopped")


app = FastAPI(
    title="Captain Taxi — BOT",
    description="ElevenLabs voice dispatcher: takes calls, books trips, escalates to humans.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health.router)
app.include_router(elevenlabs.router)
app.include_router(calls.router)
app.include_router(logs_router.router)


@app.get("/")
async def root():
    return {
        "service": "Captain Taxi BOT",
        "status": "running",
        "channels": ["phone (ElevenLabs + Twilio)"],
    }
