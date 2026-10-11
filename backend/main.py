"""
Cold Email Agent — FastAPI application entry point.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db import init_db
from backend.routers import companies, dashboard, emails

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)

import httpx
from contextlib import asynccontextmanager
from curl_cffi.requests import AsyncSession

# Global clients for extraction engine
http_client: httpx.AsyncClient | None = None
impersonated_client: AsyncSession | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, impersonated_client
    
    # Initialize DB
    init_db()
    settings = get_settings()
    logging.getLogger(__name__).info(
        f"Cold Email Agent started | DRY_RUN={settings.DRY_RUN} | "
        f"DAILY_SEND_LIMIT={settings.DAILY_SEND_LIMIT}"
    )

    # Init global HTTP clients for extraction
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    timeout = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
    http_client = httpx.AsyncClient(limits=limits, timeout=timeout, http2=True)
    
    # Impersonated client for Workday TLS Bypass leveraging BoringSSL
    impersonated_client = AsyncSession(impersonate="chrome120", timeout=15.0)
    
    # Note: Crawl4AI setup will be added later if needed
    
    yield
    
    await http_client.aclose()
    impersonated_client.close()

app = FastAPI(
    title="Cold Email Agent",
    version="1.0.0",
    description=(
        "AI-powered cold email pipeline for Rushil Reddy Chirla's "
        "Summer 2027 CPT internship search."
    ),
    lifespan=lifespan
)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(companies.router)
app.include_router(emails.router)
app.include_router(dashboard.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    """Simple health check. Returns current dry-run status."""
    settings = get_settings()
    return {
        "status": "ok",
        "dry_run": settings.DRY_RUN,
        "daily_send_limit": settings.DAILY_SEND_LIMIT,
        "sender": settings.GMAIL_FROM,
    }
