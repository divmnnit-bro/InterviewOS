from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Availability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A time window [start_time, end_time) in which a candidate or interviewer is free.

    `owner_id` points at users.id, so one table serves both roles. Overlapping
    or adjacent windows for the same owner are allowed here; the scheduler
    merges them before building the model.
    """

    __tablename__ = "availabilities"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="end_after_start"),
        Index("ix_availabilities_owner_window", "owner_id", "start_time", "end_time"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<Availability {self.owner_id} {self.start_time}..{self.end_time}>"
