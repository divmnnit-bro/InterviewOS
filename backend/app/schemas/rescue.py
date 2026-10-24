"""Request and response schemas for conflict explanations and Ripple Rescue."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.scheduler.rescue import DisruptionKind
from app.schemas.schedule import ProposeOptions, UnscheduledReasonOut


# ------------------------------------------------------------------ explain
class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: ProposeOptions = Field(default_factory=ProposeOptions)
    # Each what-if re-runs the solver on a relaxed copy of the problem, so this bounds the cost.
    max_whatifs: int = Field(default=30, ge=0, le=100)


class PlacedInterviewOut(BaseModel):
    candidate_id: uuid.UUID
    stage_id: uuid.UUID
    room_id: uuid.UUID
    interviewer_ids: list[uuid.UUID]
    start_time: datetime
    end_time: datetime


class BlockerOut(BaseModel):
    kind: str
    resource_id: uuid.UUID
    interviews: list[PlacedInterviewOut]


class FixOut(BaseModel):
    kind: str
    description: str
    target_id: uuid.UUID | None
    # How many more interviews the whole run schedules once this change is made.
    extra_interviews: int


class ExplanationOut(BaseModel):
    candidate_id: uuid.UUID
    stage_id: uuid.UUID
    reason_codes: list[str]
    summary: str
    best_slot: datetime | None
    blockers: list[BlockerOut]
    fixes: list[FixOut]


class RescuedKeyOut(BaseModel):
    candidate_id: uuid.UUID
    stage_id: uuid.UUID


class WhatIfOut(BaseModel):
    kind: str
    description: str
    target_id: uuid.UUID | None
    total_scheduled: int
    rescued: list[RescuedKeyOut]


class ExplainOut(BaseModel):
    drive_id: uuid.UUID
    schedule_version: int
    solver_status: str
    complete: bool
    scheduled: int
    unscheduled_count: int
    explanations: list[ExplanationOut]
    what_ifs: list[WhatIfOut]
    budget_exhausted: bool


# ------------------------------------------------------------------- rescue
class DisruptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: DisruptionKind
    resource_id: uuid.UUID          # the interviewer, room or candidate that is out
    start_time: AwareDatetime
    end_time: AwareDatetime

    @model_validator(mode="after")
    def _ordered(self) -> "DisruptionIn":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class DisruptionOut(BaseModel):
    kind: DisruptionKind
    resource_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    # True when the system added it because a booked room or interviewer is no longer usable.
    implicit: bool = False


class RescueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disruptions: list[DisruptionIn] = Field(min_length=1, max_length=20)
    options: ProposeOptions = Field(default_factory=ProposeOptions)


class RescueApplyRequest(RescueRequest):
    # The drive's schedule_version the coordinator saw in the preview.
    expected_version: int = Field(ge=0)
    # Optional: the fingerprint from the preview. If the plan the server computes now is not
    # exactly the one that was previewed, nothing is applied.
    plan_fingerprint: str | None = Field(default=None, min_length=1, max_length=64)


class PlacementOut(BaseModel):
    start_time: datetime
    end_time: datetime
    room_id: uuid.UUID
    interviewer_ids: list[uuid.UUID]


class MoveOut(BaseModel):
    interview_id: uuid.UUID
    candidate_id: uuid.UUID
    stage_id: uuid.UUID
    old: PlacementOut
    new: PlacementOut
    changes: list[str]                  # any of "time", "room", "panel"
    directly_affected: bool             # false = collateral: moved to make room for one that was hit
    notifies_candidate: bool


class DroppedOut(BaseModel):
    interview_id: uuid.UUID
    candidate_id: uuid.UUID
    stage_id: uuid.UUID
    reasons: list[UnscheduledReasonOut]


class RescuePlanOut(BaseModel):
    drive_id: uuid.UUID
    schedule_version: int
    solver_status: str
    fully_repaired: bool
    plan_fingerprint: str
    disruptions: list[DisruptionOut]
    affected: list[uuid.UUID]           # interviews directly hit
    moves: list[MoveOut]
    collateral_count: int
    dropped: list[DroppedOut]           # interviews that cannot be re-placed (cancelled on apply)
    needs_manual: list[uuid.UUID]       # started or locked interviews that were hit; never moved
    unchanged: list[uuid.UUID]
    candidates_to_notify: list[uuid.UUID]
    interviewers_to_notify: list[uuid.UUID]


class RescueApplyOut(RescuePlanOut):
    applied: bool                       # false when there was nothing to change
    new_schedule_version: int
    moved_count: int
    cancelled_count: int
    notifications_created: int
