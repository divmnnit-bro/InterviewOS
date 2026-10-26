from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import DriveCandidateStatus, DriveStatus, StageType
from app.schemas.common import ORMModel, require_aware, require_zone
from app.services.pipeline_rules import validate_pass_rule

# Statuses a coordinator may set by hand. `published` is reached only by publishing a schedule.
SETTABLE_STATUSES = {DriveStatus.DRAFT, DriveStatus.COLLECTING_AVAILABILITY, DriveStatus.ARCHIVED}


class DriveCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = None
    window_start: datetime
    window_end: datetime
    timezone: str = "UTC"
    slot_minutes: int = Field(default=15, ge=5, le=60)
    interviewer_buffer_minutes: int = Field(default=0, ge=0, le=240)
    min_round_gap_minutes: int = Field(default=0, ge=0, le=7 * 24 * 60)

    _aw = field_validator("window_start", "window_end")(require_aware)
    _tz = field_validator("timezone")(require_zone)

    @model_validator(mode="after")
    def _order(self) -> "DriveCreate":
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        return self


class DriveUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    timezone: str | None = None
    slot_minutes: int | None = Field(default=None, ge=5, le=60)
    interviewer_buffer_minutes: int | None = Field(default=None, ge=0, le=240)
    min_round_gap_minutes: int | None = Field(default=None, ge=0, le=7 * 24 * 60)
    status: DriveStatus | None = None

    @field_validator("window_start", "window_end")
    @classmethod
    def _aw(cls, v):
        return None if v is None else require_aware(v)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v):
        return None if v is None else require_zone(v)

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        if v is not None and v not in SETTABLE_STATUSES:
            raise ValueError("status can only be set to draft, collecting_availability or archived")
        return v


class DriveOut(ORMModel):
    id: uuid.UUID
    title: str
    description: str | None
    window_start: datetime
    window_end: datetime
    timezone: str
    slot_minutes: int
    interviewer_buffer_minutes: int
    min_round_gap_minutes: int
    status: DriveStatus
    schedule_version: int


class StageCreate(BaseModel):
    order_index: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=80)
    stage_type: StageType
    duration_minutes: int = Field(gt=0, le=480)
    panel_size: int = Field(default=1, ge=1, le=10)
    required_skills: list[str] = Field(default_factory=list, max_length=20)
    rule: dict[str, Any] | None = None

    @field_validator("rule")
    @classmethod
    def _valid_pass_rule(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_pass_rule(value)


class StageUpdate(BaseModel):
    order_index: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=80)
    stage_type: StageType | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=480)
    panel_size: int | None = Field(default=None, ge=1, le=10)
    required_skills: list[str] | None = Field(default=None, max_length=20)
    rule: dict[str, Any] | None = None

    @field_validator("rule")
    @classmethod
    def _valid_pass_rule(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_pass_rule(value)


class StageOut(ORMModel):
    id: uuid.UUID
    drive_id: uuid.UUID
    order_index: int
    name: str
    stage_type: StageType
    duration_minutes: int
    panel_size: int
    required_skills: list[str]
    rule: dict[str, Any]


class EnrollRequest(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(min_length=1, max_length=2000)


class EnrollmentOut(ORMModel):
    candidate_id: uuid.UUID
    status: DriveCandidateStatus
    current_stage_id: uuid.UUID | None


class PanelMemberOut(BaseModel):
    id: uuid.UUID
    name: str


class DriveInterviewDetailOut(BaseModel):
    id: uuid.UUID
    drive_id: uuid.UUID
    stage_id: uuid.UUID
    stage_name: str
    candidate_id: uuid.UUID
    candidate_name: str
    room_id: uuid.UUID | None = None
    room_name: str | None = None
    panel: list[PanelMemberOut] = []
    start_time: datetime
    end_time: datetime
    status: Any
    version: int
