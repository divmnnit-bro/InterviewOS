from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class JobOut(ORMModel):
    id: uuid.UUID
    job_type: str
    status: str
    progress: int
    progress_message: str | None = None
    error_message: str | None = None
    payload: dict[str, Any] = {}
    result: dict[str, Any] | None = None
    retry_count: int = 0
    max_retries: int = 3
    idempotency_key: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class JobSummaryOut(BaseModel):
    id: uuid.UUID
    job_type: str
    status: str
    progress: int
    progress_message: str | None = None
    is_done: bool


class JobCancelResponse(BaseModel):
    job_id: uuid.UUID
    cancelled: bool
    message: str
