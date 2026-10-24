from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import DriveCandidateStatus
from app.services.pipeline_rules import StageState


class CandidateStageDecision(BaseModel):
    """A coordinator's decision about one candidate in one round.

    `stage_id` is the round being decided and must be the candidate's current round, so a double
    click or a stale screen cannot advance a candidate twice. A pass that lacks evidence (no interview,
    feedback missing, average below the round's minimum) is refused unless `override` is true with a reason.
    """

    stage_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=2000)
    override: bool = False
    override_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _override_needs_a_reason(self) -> "CandidateStageDecision":
        if self.override and len((self.override_reason or "").strip()) < 10:
            raise ValueError("override_reason (at least 10 characters) is required when override is true")
        return self


class DecisionOut(BaseModel):
    drive_id: uuid.UUID
    candidate_id: uuid.UUID
    outcome: Literal["advanced", "selected", "rejected"]
    status: DriveCandidateStatus
    from_stage_id: uuid.UUID
    current_stage_id: uuid.UUID | None
    average_score: float | None
    rule_met: bool | None
    override_used: bool
    cancelled_interviews: int = 0


class StageProgress(BaseModel):
    stage_id: uuid.UUID
    order_index: int
    name: str
    state: StageState
    interview_id: uuid.UUID | None
    interview_status: str | None
    evaluations: int
    average_score: float | None
    rule_met: bool | None


class PipelineCandidate(BaseModel):
    candidate_id: uuid.UUID
    name: str
    email: str
    status: DriveCandidateStatus
    current_stage_id: uuid.UUID | None
    stages: list[StageProgress]


class PipelineStageSummary(BaseModel):
    stage_id: uuid.UUID
    order_index: int
    name: str
    candidates_here: int         # active candidates whose current round this is
    awaiting_decision: int
    passed: int
    rejected: int


class PipelineStatusResponse(BaseModel):
    drive_id: uuid.UUID
    title: str
    status_counts: dict[str, int]
    stages: list[PipelineStageSummary]
    candidates: list[PipelineCandidate]
