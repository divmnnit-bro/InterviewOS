from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ Overview
class UpcomingInterviewOut(BaseModel):
    interview_id: uuid.UUID
    drive_id: uuid.UUID
    drive_title: str
    stage_name: str
    candidate_name: str
    room_name: str | None = None
    start_time: datetime
    end_time: datetime


class RecentActivityOut(BaseModel):
    action: str
    entity_type: str
    timestamp: datetime


class AnalyticsOverviewOut(BaseModel):
    total_drives: int
    active_drives: int
    completed_drives: int
    total_candidates_registered: int
    total_candidates_enrolled: int
    total_interviews_scheduled: int
    total_interviews_completed: int
    global_completion_rate: float
    total_evaluations_submitted: int
    average_score_across_all_evaluations: float | None = None
    pending_evaluations_count: int = 0
    upcoming_interviews: list[UpcomingInterviewOut] = Field(default_factory=list)
    recent_activity: list[RecentActivityOut] = Field(default_factory=list)
    generated_at: str


# ------------------------------------------------------------------ Drive Analytics
class StageFunnelItem(BaseModel):
    stage_id: uuid.UUID
    stage_name: str
    order_index: int
    stage_type: str
    candidates_count: int
    passed_count: int
    failed_count: int
    pending_count: int
    conversion_rate: float


class DriveAnalyticsOut(BaseModel):
    drive_id: uuid.UUID
    drive_title: str
    drive_status: str
    timezone: str
    window_start: str
    window_end: str
    total_enrolled: int
    active_in_pipeline: int
    selected_count: int
    rejected_count: int
    withdrawn_count: int
    overall_selection_rate: float
    interview_completion_rate: float
    total_interviews: int
    completed_interviews: int
    cancelled_interviews: int
    pending_feedback_count: int
    stage_funnel: list[StageFunnelItem] = Field(default_factory=list)
    average_stage_duration_hours: float = 0.0
    room_utilization_percent: float = 0.0
    rescue_operations_count: int = 0
    generated_at: str


# ------------------------------------------------------------------ Stage Analytics
class StageAnalyticsItem(BaseModel):
    stage_id: uuid.UUID
    stage_name: str
    order_index: int
    stage_type: str
    duration_minutes: int
    panel_size: int
    total_candidates_entered: int
    conversion_rate: float
    dropoff_rate: float
    average_score: float | None = None
    min_score: float | None = None
    max_score: float | None = None
    median_score: float | None = None
    interviews_completed: int
    interviews_scheduled: int


class StagesAnalyticsOut(BaseModel):
    drive_id: uuid.UUID
    drive_title: str
    stages: list[StageAnalyticsItem] = Field(default_factory=list)
    generated_at: str


# ------------------------------------------------------------------ Interviewer Analytics
class InterviewerAnalyticsItem(BaseModel):
    interviewer_id: uuid.UUID
    name: str
    email: str
    department: str
    capacity_per_day: int
    skills: list[str] = Field(default_factory=list)
    total_assigned_interviews: int
    completed_interviews: int
    pending_evaluations: int
    utilization_rate: float
    average_score_given: float | None = None
    evaluator_calibration: str  # "calibrated", "harsh", "generous"


class InterviewersAnalyticsOut(BaseModel):
    total_interviewers: int
    interviewers: list[InterviewerAnalyticsItem] = Field(default_factory=list)
    generated_at: str
