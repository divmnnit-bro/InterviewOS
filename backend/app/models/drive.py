from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import DriveStatus, pg_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.drive_candidate import DriveCandidate
    from app.models.stage import InterviewStage


class RecruitmentDrive(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A placement drive: a scheduling window plus an ordered list of stages.

    `schedule_version` counts published schedule changes. It is NOT an ORM
    version column on purpose: services bump it with a compare-and-swap
    (UPDATE ... WHERE id = :id AND schedule_version = :expected), so a proposal
    generated against an old version is rejected at publish time.
    """

    __tablename__ = "recruitment_drives"
    __table_args__ = (
        CheckConstraint("window_end > window_start", name="window_valid"),
        CheckConstraint("schedule_version >= 0", name="schedule_version_non_negative"),
        CheckConstraint("slot_minutes BETWEEN 5 AND 60", name="slot_minutes_range"),
        CheckConstraint(
            "interviewer_buffer_minutes >= 0 AND min_round_gap_minutes >= 0", name="rules_non_negative"),
    )

    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[DriveStatus] = mapped_column(
        pg_enum(DriveStatus, "drive_status"),
        default=DriveStatus.DRAFT,
        nullable=False,
        index=True,
    )
    # IANA zone that defines what "a day" means for interviewers' daily limits.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC", server_default="UTC"
    )
    # Scheduling rules shared by the solver AND self-booking, so both enforce the same grid and rest time.
    slot_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15, server_default="15")
    interviewer_buffer_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0")
    min_round_gap_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0")
    schedule_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    stages: Mapped[list[InterviewStage]] = relationship(
        back_populates="drive",
        order_by="InterviewStage.order_index",
        cascade="all, delete-orphan",
    )
    enrollments: Mapped[list[DriveCandidate]] = relationship(
        back_populates="drive", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<RecruitmentDrive {self.title!r} {self.status.value} v{self.schedule_version}>"
