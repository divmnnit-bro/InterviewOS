from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

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
    # Configurable soft-constraint weights
    earliness_weight: int | None = Field(default=None, ge=0)
    load_balance_weight: int | None = Field(default=None, ge=0)
    room_fit_weight: int | None = Field(default=None, ge=0)


class ScheduleQualityReportOut(BaseModel):
    total_requested: int
    scheduled_count: int
    unscheduled_count: int
    completion_rate: float
    hard_constraint_violations: int
    violation_details: list[str] = []
    interviewer_workload_variance: float
    interviewer_workload_std_dev: float
    max_interviewer_load: int
    min_interviewer_load: int
    room_utilization_percent: float
    average_candidate_wait_hours: float
    schedule_changes_count: int = 0
    is_verified: bool


class ScheduleComparisonOut(BaseModel):
    added_count: int
    moved_count: int
    unchanged_count: int
    cancelled_count: int
    details: list[dict[str, Any]] = []


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
    wall_time_seconds: float | None = None
    interviews: list[ProposedInterviewOut]
    unscheduled: list[UnscheduledOut] = []
    quality_report: ScheduleQualityReportOut | None = None
    comparison: ScheduleComparisonOut | None = None


class PublishRequest(BaseModel):
    expected_version: int = Field(ge=0)


class PublishOut(BaseModel):
    drive_id: uuid.UUID
    schedule_version: int
    published_interviews: int
    superseded_dropped: int = 0   # proposed interviews dropped because the candidate had self-booked
