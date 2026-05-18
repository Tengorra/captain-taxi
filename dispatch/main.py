"""
Captain Taxi — Dispatch Service
================================
Entry point.  Run with:
    uvicorn main:app --host 0.0.0.0 --port 8001 --reload
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from database import create_tables
from redis_client import close_redis
from routes.dispatch import router as dispatch_router
from routes.driver import router as driver_router
from routes.dashboard import router as dashboard_router
from services.timeout_worker import run_timeout_worker
from services.scheduler import run_prebook_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()

_timeout_task: asyncio.Task | None = None
_prebook_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("Starting Captain Taxi Dispatch Service")
    await create_tables()
    global _timeout_task, _prebook_task
    _timeout_task = asyncio.create_task(run_timeout_worker())
    _prebook_task = asyncio.create_task(run_prebook_scheduler())
    logger.info("Background workers launched (timeout, pre-booking scheduler)")
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────
    for task in (_timeout_task, _prebook_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    await close_redis()
    logger.info("Dispatch service shut down cleanly")


app = FastAPI(
    title="Captain Taxi — Dispatch API",
    description=(
        "AI-powered dispatch system for Captain Taxi (Saskatoon & Regina). "
        "Manages trip lifecycle, driver assignment, real-time location tracking, "
        "and SMS notifications."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dispatch_router)
app.include_router(driver_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "captain-taxi-dispatch"}


@app.get("/")
async def root():
    return {
        "service": "Captain Taxi Dispatch",
        "version": "1.0.0",
        "docs": "/docs",
    }
