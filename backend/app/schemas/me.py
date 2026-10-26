from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.enums import DriveCandidateStatus


class MyInterviewOut(BaseModel):
    id: uuid.UUID
    drive_id: uuid.UUID
    drive_title: str
    stage_id: uuid.UUID
    stage_name: str
    room_id: uuid.UUID | None = None
    room_name: str | None = None
    start_time: datetime
    end_time: datetime
    status: Any
    version: int
    candidate_name: str | None = None  # Populated for interviewer view
    panel_names: list[str] = []        # Populated for candidate view
    evaluation_submitted: bool | None = None  # Interviewer's own feedback status; hidden from candidates


class DecidedRoundResult(BaseModel):
    stage_id: uuid.UUID
    stage_name: str
    order_index: int
    result: Literal["advanced", "selected", "not_selected"] | None = None


class CandidateDriveProgressOut(BaseModel):
    drive_id: uuid.UUID
    drive_title: str
    enrolment_status: DriveCandidateStatus
    current_stage_id: uuid.UUID | None = None
    current_stage_name: str | None = None
    rounds: list[DecidedRoundResult] = []
