"""
Captain Taxi — Accounts Agent
Handles driver pay, invoicing, QuickBooks sync, and financial reporting.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import create_tables
from routers import driver_pay_router, invoices_router, quickbooks_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Captain Taxi Accounts Agent starting up...")
    create_tables()
    logger.info("Database tables ready.")
    yield
    logger.info("Accounts Agent shut down.")


app = FastAPI(
    title="Captain Taxi — Accounts Agent",
    description="Driver pay, invoicing, QuickBooks integration, and financial reporting.",
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

app.include_router(driver_pay_router.router, prefix="/api")
app.include_router(invoices_router.router, prefix="/api")
app.include_router(quickbooks_router.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "accounts-agent"}


@app.get("/")
async def root():
    return {"service": "Captain Taxi Accounts Agent", "docs": "/docs", "health": "/health"}
