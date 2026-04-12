"""
Captain Taxi — Driver Management Agent
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from tasks.scheduler import scheduler, setup_jobs
from routers import drivers, onboarding, scheduling, performance, communication, webhooks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Captain Taxi Driver Agent starting up...")
    await init_db()
    logger.info("Database tables initialized.")
    setup_jobs()
    scheduler.start()
    logger.info("Scheduler started.")
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shut down.")


app = FastAPI(
    title="Captain Taxi — Driver Management Agent",
    description=(
        "Manages driver onboarding, scheduling, performance tracking, "
        "and communication for Captain Taxi (Saskatoon & Regina, SK)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(drivers.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(scheduling.router, prefix="/api")
app.include_router(performance.router, prefix="/api")
app.include_router(communication.router, prefix="/api")
app.include_router(webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "driver-management-agent"}


@app.get("/")
async def root():
    return {
        "service": "Captain Taxi Driver Management Agent",
        "docs": "/docs",
        "health": "/health",
    }
