from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import Recommendation
from app.schemas.common import ORMModel

RUBRIC_MAX_CRITERIA = 20
Rating = Annotated[float, Field(ge=0, le=10, allow_inf_nan=False)]


class EvaluationCreate(BaseModel):
    """One interviewer's feedback on one interview.

    Give per-criterion `rubric` ratings (each 0-10), an overall `score` (0-10), or both. If `score`
    is left out it is the mean of the rubric ratings. A recommendation is always required.
    """

    rubric: dict[str, Rating] = Field(default_factory=dict, max_length=RUBRIC_MAX_CRITERIA)
    score: float | None = Field(default=None, ge=0, le=10, allow_inf_nan=False)
    feedback: str | None = Field(default=None, max_length=5000)
    recommendation: Recommendation
    # Coordinators only: the panel member this feedback is recorded for.
    on_behalf_of: uuid.UUID | None = None

    @field_validator("rubric")
    @classmethod
    def _clean_rubric(cls, value: dict[str, float]) -> dict[str, float]:
        cleaned: dict[str, float] = {}
        seen: set[str] = set()
        for name, rating in value.items():
            name = name.strip()
            if not name or len(name) > 64:
                raise ValueError("criterion names must be 1-64 characters")
            if name.lower() in seen:
                raise ValueError(f"criterion {name!r} appears more than once")
            seen.add(name.lower())
            cleaned[name] = float(rating)
        return cleaned

    @field_validator("feedback")
    @classmethod
    def _blank_feedback_is_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def _needs_a_rating(self) -> "EvaluationCreate":
        if not self.rubric and self.score is None:
            raise ValueError("give rubric ratings, an overall score, or both")
        return self

    def overall_score(self) -> float:
        if self.score is not None:
            return round(self.score, 2)
        value = round(sum(self.rubric.values()) / len(self.rubric), 2)
        return 0.0 if math.isnan(value) else value


class EvaluationRead(ORMModel):
    id: uuid.UUID
    interview_id: uuid.UUID
    interviewer_id: uuid.UUID          # the author
    score: float
    rubric: dict[str, float]
    feedback: str | None
    recommendation: Recommendation | None
    submitted_at: datetime
    updated_at: datetime


class InterviewEvaluationsOut(BaseModel):
    interview_id: uuid.UUID
    # "all": every submission is shown. "own_only": a panelist who has not submitted yet sees
    # nothing from colleagues, so feedback is written independently (no anchoring).
    visibility: Literal["all", "own_only"]
    panel_size: int
    submitted_count: int
    evaluations: list[EvaluationRead]
