from __future__ import annotations

import logging
import time
from typing import Any
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.services.errors import ServiceError
from app.services.job_queue import recover_stale_jobs
from app.services.redis_service import is_redis_healthy

log = logging.getLogger("interviewos.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: recover any stale jobs from previous worker crashes/restarts
    try:
        recover_stale_jobs()
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to recover stale jobs on startup: %s", exc)
    yield
    # Shutdown logic if needed


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.include_router(api_router)


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    t0 = time.perf_counter()

    response = await call_next(request)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"

    # Structured observability log (ignoring health probe spam)
    if request.url.path not in ("/health", "/docs", "/openapi.json"):
        log.info(
            "request_id=%s method=%s path=%s status=%d duration_ms=%.2f",
            req_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
    return response


if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        allow_credentials=False,
        expose_headers=["Content-Disposition", "X-Request-ID", "X-Response-Time-Ms"],
        max_age=600,
    )


@app.exception_handler(ServiceError)
async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    body = {"error": exc.code, "message": exc.message}
    if exc.details is not None:
        body["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=body)


@app.get("/health", tags=["meta"])
def health() -> dict[str, Any]:
    redis_ok = is_redis_healthy()
    return {
        "status": "ok",
        "redis": "healthy" if redis_ok else "fallback_in_memory",
        "environment": settings.ENVIRONMENT,
        "scheduler_max_workers": settings.SCHEDULER_MAX_WORKERS,
    }