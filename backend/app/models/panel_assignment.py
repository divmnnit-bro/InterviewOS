from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.interview import Interview
    from app.models.interviewer import Interviewer


class PanelAssignment(TimestampMixin, Base):
    """Links an interviewer to an interview.

    `start_time` / `end_time` are copies of the interview's slot. They exist so
    the database can reject an interviewer being in two overlapping interviews
    (an exclusion constraint cannot look across tables). The composite foreign
    key to interviews(id, start_time, end_time) with ON UPDATE CASCADE keeps the
    copies correct: if an interview is moved, its panel rows move with it.

    `is_active` must be set to False by the service when the interview is
    cancelled, which frees the interviewer's slot while keeping history.
    """

    __tablename__ = "panel_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["interview_id", "start_time", "end_time"],
            ["interviews.id", "interviews.start_time", "interviews.end_time"],
            name="fk_panel_assignments_interview_slot",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        ExcludeConstraint(
            ("interviewer_id", "="),
            (func.tstzrange(text("start_time"), text("end_time"), "[)"), "&&"),
            where=text("is_active"),
            using="gist",
            name="ex_panel_assignments_interviewer_no_overlap",
        ),
    )

    interview_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    interviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interviewers.user_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    interview: Mapped[Interview] = relationship(back_populates="panel")
    interviewer: Mapped[Interviewer] = relationship(back_populates="panel_assignments")

    def __repr__(self) -> str:
        return f"<PanelAssignment interview={self.interview_id} interviewer={self.interviewer_id}>"
