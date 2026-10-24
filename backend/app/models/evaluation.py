from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import Recommendation, pg_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.interview import Interview
    from app.models.interviewer import Interviewer


class Evaluation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One interviewer's rubric-based evaluation of one interview.

    `score` is the overall result on a 0-10 scale; `rubric` holds the
    per-criterion breakdown. Access control (who may read feedback) is enforced
    in the API layer, not here.
    """

    __tablename__ = "evaluations"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 10", name="score_range"),
        UniqueConstraint("interview_id", "interviewer_id", name="uq_evaluations_interview_interviewer"),
    )

    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interviewers.user_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    score: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    rubric: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    feedback: Mapped[str | None] = mapped_column(Text)
    # Nullable only so rows written before migration 0004 stay valid; the API always requires it.
    recommendation: Mapped[Recommendation | None] = mapped_column(
        pg_enum(Recommendation, "evaluation_recommendation")
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    interview: Mapped[Interview] = relationship(back_populates="evaluations")
    interviewer: Mapped[Interviewer] = relationship(back_populates="evaluations")

    def __repr__(self) -> str:
        return f"<Evaluation interview={self.interview_id} score={self.score}>"
