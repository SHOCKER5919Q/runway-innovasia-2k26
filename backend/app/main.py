"""RUNWAY API entry point."""
from __future__ import annotations

import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.db import create_all
from app.core.security import rate_limiter

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.INFO,
    format='{"t":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    stream=sys.stdout)
log = logging.getLogger("runway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    log.info("RUNWAY %s starting (env=%s, db=%s)", settings.version, settings.env,
             settings.database_url.split("///")[-1])
    yield
    log.info("RUNWAY shutting down")


app = FastAPI(
    title="RUNWAY - Financial Intelligence OS for Indian MSMEs",
    version=settings.version,
    description=(
        "Three-state financial intelligence: ACTUAL (what is recorded), "
        "PREDICTED (what is likely) and SIMULATED (what could happen). "
        "Every financial figure returned by this API is computed from the "
        "business's own ledger by a deterministic engine."),
    lifespan=lifespan,
    docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-Response-Time-Ms"])


@app.middleware("http")
async def observability(request: Request, call_next):
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
    t0 = time.perf_counter()
    client = request.client.host if request.client else "anon"
    if request.url.path.startswith("/api/") and not rate_limiter.allow(f"http:{client}"):
        return JSONResponse(status_code=429,
                            content={"detail": "Rate limit exceeded"},
                            headers={"X-Request-Id": rid})
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error rid=%s path=%s", rid, request.url.path)
        return JSONResponse(status_code=500,
                            content={"detail": "Internal error", "request_id": rid},
                            headers={"X-Request-Id": rid})
    ms = int((time.perf_counter() - t0) * 1000)
    response.headers["X-Request-Id"] = rid
    response.headers["X-Response-Time-Ms"] = str(ms)
    if request.url.path.startswith("/api/"):
        log.info("%s %s -> %s in %dms rid=%s", request.method, request.url.path,
                 response.status_code, ms, rid)
    return response


from app.api import (  # noqa: E402
    routes_auth, routes_copilot, routes_core, routes_integrations,
    routes_intelligence, routes_ledger, routes_reports, routes_scenarios,
)

for r in (routes_auth.router, routes_core.router, routes_ledger.router,
          routes_intelligence.router, routes_scenarios.router,
          routes_copilot.router, routes_integrations.router,
          routes_reports.router, routes_reports.public_router):
    app.include_router(r)


@app.get("/health", tags=["meta"])
def health():
    from sqlalchemy import text
    from app.core.db import engine
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "version": settings.version,
            "env": settings.env, "database": "ok" if db_ok else "unreachable"}


@app.get("/api/meta", tags=["meta"])
def meta():
    from app.copilot import llm
    from app.digital_twin.scenario_engine import CATALOGUE
    from app.integrations.base import PLANNED, REGISTRY
    return {
        "name": "RUNWAY", "version": settings.version, "env": settings.env,
        "capabilities": {
            "three_state_architecture": True,
            "monte_carlo_paths_default": settings.monte_carlo_paths,
            "forecast_horizon_weeks": settings.forecast_horizon_weeks,
            "scenario_types": len(CATALOGUE),
            "import_adapters_available": sum(1 for a in REGISTRY.values()
                                             if a.status == "available"),
            "integrations_declared_future": len(PLANNED),
            "copilot_llm_configured": llm.available(),
        },
        "principles": [
            "Every financial figure is computed from the ledger, never hardcoded.",
            "Actual, predicted and simulated are separated in the database, the API "
            "and the interface.",
            "A model ships only if it beats its baseline by a statistically "
            "significant margin.",
            "No accuracy figure is published that has not been measured.",
            "RUNWAY never moves money, borrows, or changes a contract.",
        ],
    }
