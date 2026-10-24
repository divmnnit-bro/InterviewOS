from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import InterviewStatus, pg_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.evaluation import Evaluation
    from app.models.panel_assignment import PanelAssignment
    from app.models.room import Room
    from app.models.stage import InterviewStage

# Rows that still occupy their slot. Cancelled / no-show interviews free it.
_ACTIVE = "status NOT IN ('cancelled', 'no_show')"


class Interview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A scheduled session for one candidate in one stage, in one room.

    The slot is stored as [start_time, end_time). Double booking is blocked by
    the database itself with PostgreSQL exclusion constraints, so even two
    simultaneous requests cannot both win the same room or candidate slot.
    This requires the `btree_gist` extension (created in the first migration).

    `version` is an optimistic-lock counter: SQLAlchemy increments it on every
    UPDATE and raises StaleDataError if another transaction changed the row
    first, which is how the backend revalidates against the latest schedule.

    Panel members live in `PanelAssignment`, which carries its own copy of the
    slot (kept in sync by a composite foreign key to the UNIQUE (id, start_time,
    end_time) constraint below) so interviewer overlaps are blocked too.
    """

    __tablename__ = "interviews"

    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_stages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="SET NULL"), index=True
    )

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[InterviewStatus] = mapped_column(
        pg_enum(InterviewStatus, "interview_status"),
        default=InterviewStatus.PROPOSED,
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Retry-safe bookings: the same key can never create a second interview.
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)

    stage: Mapped[InterviewStage] = relationship(back_populates="interviews")
    candidate: Mapped[Candidate] = relationship(back_populates="interviews")
    room: Mapped[Room | None] = relationship(back_populates="interviews")
    panel: Mapped[list[PanelAssignment]] = relationship(
        back_populates="interview", cascade="all, delete-orphan", passive_deletes=True
    )
    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="interview", cascade="all, delete-orphan", passive_deletes=True
    )

    __mapper_args__ = {"version_id_col": version}

    __table_args__ = (
        CheckConstraint("end_time > start_time", name="end_after_start"),
        # Target for PanelAssignment's composite foreign key.
        UniqueConstraint("id", "start_time", "end_time", name="uq_interviews_id_slot"),
        Index("ix_interviews_start_end", "start_time", "end_time"),
        # No two active interviews may use the same room at overlapping times.
        ExcludeConstraint(
            ("room_id", "="),
            (func.tstzrange(text("start_time"), text("end_time"), "[)"), "&&"),
            where=text(_ACTIVE),
            using="gist",
            name="ex_interviews_room_no_overlap",
        ),
        # A candidate cannot be in two active interviews at the same time.
        ExcludeConstraint(
            ("candidate_id", "="),
            (func.tstzrange(text("start_time"), text("end_time"), "[)"), "&&"),
            where=text(_ACTIVE),
            using="gist",
            name="ex_interviews_candidate_no_overlap",
        ),
    )

    def __repr__(self) -> str:
        return f"<Interview {self.id} {self.status.value} v{self.version}>"
