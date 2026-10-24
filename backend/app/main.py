from __future__ import annotations

from fastapi import FastAPI, Request
<<<<<<< HEAD
from fastapi.middleware.cors import CORSMiddleware
=======
>>>>>>> 8136b20f43f8a14c8c87bbe0b298e6f4acc0f56d
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.services.errors import ServiceError

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(api_router)

<<<<<<< HEAD
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        allow_credentials=False,
        expose_headers=["Content-Disposition"],
        max_age=600,
    )

=======
>>>>>>> 8136b20f43f8a14c8c87bbe0b298e6f4acc0f56d

@app.exception_handler(ServiceError)
async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    body = {"error": exc.code, "message": exc.message}
    if exc.details is not None:
        body["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=body)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
