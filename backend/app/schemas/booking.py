from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import InterviewStatus
from app.schemas.common import require_aware


class IssueLinksRequest(BaseModel):
    candidate_ids: list[uuid.UUID] | None = Field(default=None, max_length=2000)  # None = every eligible candidate
    ttl_hours: int = Field(default=72, ge=1, le=24 * 30)


class LinkOut(BaseModel):
    candidate_id: uuid.UUID
    token: str
    path: str                      # append to your front-end base URL


class SkippedOut(BaseModel):
    candidate_id: uuid.UUID
    reason: str


class IssueLinksOut(BaseModel):
    links: list[LinkOut]
    skipped: list[SkippedOut]


class SlotOut(BaseModel):
    start: datetime
    end: datetime


class BookedOut(BaseModel):
    interview_id: uuid.UUID
    stage_id: uuid.UUID
    start: datetime
    end: datetime
    status: InterviewStatus
    room: str | None
    location: str | None


class OffersOut(BaseModel):
    stage_name: str
    duration_minutes: int
    timezone: str
    booked: BookedOut | None
    slots: list[SlotOut]


class ConfirmRequest(BaseModel):
    start: datetime

    _aw = field_validator("start")(require_aware)
