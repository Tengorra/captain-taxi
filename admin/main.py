"""
Captain Taxi — Admin Agent API
FastAPI application entry point.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from .db.database import init_db
from .scheduler import setup_scheduler
from .agents.whatsapp_handler import register_owner_numbers
from .api.routes import (
    dashboard, drivers, escalations, compliance, reports, announcements, settings, hr
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    register_owner_numbers()
    setup_scheduler()
    print("[Admin API] Started — Captain Taxi Admin System")
    yield
    # Shutdown
    from .scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(
    title="Captain Taxi Admin API",
    description="Admin Agent and Dashboard API for Captain Taxi (Saskatoon & Regina)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(dashboard.router, prefix="/api")
app.include_router(drivers.router, prefix="/api")
app.include_router(escalations.router, prefix="/api")
app.include_router(compliance.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(announcements.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(hr.router, prefix="/api")


@app.get("/")
def root():
    return {"status": "ok", "service": "Captain Taxi Admin API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
