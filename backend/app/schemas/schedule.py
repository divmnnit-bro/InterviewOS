from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import InterviewStatus
from app.schemas.common import ORMModel


class ProposeOptions(BaseModel):
    # None = use the drive's own rule (what self-booking also uses). Set only to override for one run.
    slot_minutes: int | None = Field(default=None, ge=5, le=60)
    interviewer_buffer_minutes: int | None = Field(default=None, ge=0, le=240)
    min_round_gap_minutes: int | None = Field(default=None, ge=0, le=7 * 24 * 60)
    time_limit_seconds: float = Field(default=20.0, gt=0)   # capped by SCHEDULER_MAX_TIME_LIMIT_SECONDS
    workers: int = Field(default=1, ge=1)                   # capped by SCHEDULER_MAX_WORKERS


class UnscheduledReasonOut(BaseModel):
    code: str
    detail: str


class UnscheduledOut(BaseModel):
    candidate_id: uuid.UUID
    stage_id: uuid.UUID
    reasons: list[UnscheduledReasonOut]


class ProposedInterviewOut(ORMModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    stage_id: uuid.UUID
    room_id: uuid.UUID | None
    start_time: datetime
    end_time: datetime
    status: InterviewStatus
    interviewer_ids: list[uuid.UUID]


class ProposalOut(BaseModel):
    drive_id: uuid.UUID
    # Echo this back as `expected_version` when publishing.
    schedule_version: int
    solver_status: str | None = None
    complete: bool | None = None
    interviews: list[ProposedInterviewOut]
    unscheduled: list[UnscheduledOut] = []


class PublishRequest(BaseModel):
    expected_version: int = Field(ge=0)


class PublishOut(BaseModel):
    drive_id: uuid.UUID
    schedule_version: int
    published_interviews: int
    superseded_dropped: int = 0   # proposed interviews dropped because the candidate had self-booked
