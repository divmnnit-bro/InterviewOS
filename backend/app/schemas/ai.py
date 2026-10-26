from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ Interview Kit Schemas
class CodingSampleIO(BaseModel):
    input: str
    output: str
    explanation: str = ""


class CodingQuestion(BaseModel):
    title: str
    difficulty: str  # beginner, intermediate, advanced
    description: str
    constraints: list[str] = Field(default_factory=list)
    sample_inputs_outputs: list[CodingSampleIO] = Field(default_factory=list)
    expected_concepts: list[str] = Field(default_factory=list)
    edge_cases: list[str] = Field(default_factory=list)
    evaluation_rubric: dict[str, str] = Field(
        default_factory=lambda: {
            "correctness": "Solves problem within edge cases and constraints",
            "time_complexity": "Optimal big-O time complexity",
            "code_style": "Clean, idiomatic code and variable naming",
        }
    )


class SystemDesignScenario(BaseModel):
    title: str
    problem_statement: str
    functional_requirements: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    scalability_concerns: list[str] = Field(default_factory=list)
    evaluation_criteria: dict[str, str] = Field(
        default_factory=lambda: {
            "architecture": "Clear separation of components and communication protocols",
            "data_storage": "Appropriate choice of database, schema, and caching layer",
            "resilience": "Fault tolerance, replication, and disaster recovery plan",
        }
    )


class BehavioralQuestion(BaseModel):
    question: str
    competency: str  # e.g., Ownership, Collaboration, Dealing with Ambiguity
    situation_guidance: str
    evaluation_rubric: str


class InterviewKitRequest(BaseModel):
    drive_id: uuid.UUID
    stage_id: uuid.UUID | None = None
    job_description: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    difficulty: str = Field(default="intermediate", pattern="^(beginner|intermediate|advanced|comprehensive)$")
    topic: str | None = None
    async_mode: bool = False


class InterviewKitResponse(BaseModel):
    kit_id: uuid.UUID | None = None
    drive_id: uuid.UUID | None = None
    stage_name: str | None = None
    difficulty: str = "intermediate"
    topic: str = "Technical Assessment"
    coding_questions: list[CodingQuestion] = Field(default_factory=list)
    system_design_scenarios: list[SystemDesignScenario] = Field(default_factory=list)
    behavioral_questions: list[BehavioralQuestion] = Field(default_factory=list)
    rubric_template: dict[str, Any] = Field(default_factory=dict)
    provider_used: str = "deterministic"
    model_used: str = "local"
    is_ai_generated: bool = False
    job_id: uuid.UUID | None = None


# ------------------------------------------------------------------ Drive Brief Schemas
class CandidateCountsBreakdown(BaseModel):
    total_enrolled: int
    active_in_pipeline: int
    selected: int
    rejected: int
    withdrawn: int


class UpcomingRoundBrief(BaseModel):
    stage_id: uuid.UUID
    stage_name: str
    order_index: int
    scheduled_interviews: int
    completed_interviews: int


class MissingFeedbackItem(BaseModel):
    interview_id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_name: str
    interviewer_id: uuid.UUID
    interviewer_name: str
    stage_name: str
    scheduled_time: str


class DriveBriefRequest(BaseModel):
    drive_id: uuid.UUID


class DriveBriefResponse(BaseModel):
    drive_id: uuid.UUID
    drive_title: str
    drive_status: str
    candidate_counts: CandidateCountsBreakdown
    upcoming_rounds: list[UpcomingRoundBrief] = Field(default_factory=list)
    missing_feedback: list[MissingFeedbackItem] = Field(default_factory=list)
    scheduling_conflicts_and_risks: list[str] = Field(default_factory=list)
    pending_actions: list[str] = Field(default_factory=list)
    executive_summary: str
    provider_used: str
    is_ai_generated: bool = False


# ------------------------------------------------------------------ Candidate Summary Schemas
class RoundEvaluationSummary(BaseModel):
    stage_name: str
    order_index: int
    score: float | None = None
    recommendation: str | None = None
    interviewer_name: str | None = None
    key_feedback: str | None = None


class CandidateSummaryRequest(BaseModel):
    drive_id: uuid.UUID
    candidate_id: uuid.UUID


class CandidateSummaryResponse(BaseModel):
    candidate_id: uuid.UUID
    candidate_name: str
    candidate_email: str
    drive_id: uuid.UUID
    drive_title: str
    pipeline_status: str
    current_stage_name: str | None = None
    average_score: float | None = None
    evaluations_count: int
    completed_rounds: list[RoundEvaluationSummary] = Field(default_factory=list)
    recurring_strengths: list[str] = Field(default_factory=list)
    recurring_weaknesses: list[str] = Field(default_factory=list)
    recommendation_synthesis: str
    progression_readiness: str
    disclaimer: str = (
        "This summary is an aid based on human evaluations. The human coordinator retains final decision authority."
    )
    provider_used: str
    is_ai_generated: bool = False


# ------------------------------------------------------------------ Ask AI Schemas
class AskRecruitmentDataRequest(BaseModel):
    drive_id: uuid.UUID | None = None
    question: str = Field(min_length=3, max_length=1000)


class AskRecruitmentDataResponse(BaseModel):
    question: str
    answer: str
    data_points: list[dict[str, Any]] = Field(default_factory=list)
    data_points_analyzed: int = 0
    suggested_followups: list[str] = Field(default_factory=list)
    intent: str
    provider_used: str
    is_ai_generated: bool = False
