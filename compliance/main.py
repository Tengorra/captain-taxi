"""
Captain Taxi — Compliance Agent
Tracks documents, expiry dates, and regulatory compliance for
drivers and vehicles in Saskatoon and Regina, Saskatchewan.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from compliance.database import init_db
from compliance.services.scheduler import scheduler, setup_jobs
from compliance.routers import documents, reports, alerts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Captain Taxi Compliance Agent starting up...")
    await init_db()
    logger.info("Database ready.")
    setup_jobs()
    scheduler.start()
    logger.info("Compliance scheduler started.")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Compliance Agent shut down.")


app = FastAPI(
    title="Captain Taxi — Compliance Agent",
    description=(
        "Tracks driver and vehicle compliance documents, expiry alerts, "
        "and auto-suspension for Captain Taxi (Saskatoon & Regina, SK)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "compliance-agent"}


@app.get("/")
async def root():
    return {
        "service": "Captain Taxi Compliance Agent",
        "docs": "/docs",
        "health": "/health",
    }
