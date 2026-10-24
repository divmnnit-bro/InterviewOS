from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RoomAvailability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A window [start_time, end_time) in which a room can be used.

    A room with NO rows here is open for the whole drive window. A room with
    at least one row can only be used inside its windows.
    """

    __tablename__ = "room_availabilities"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="end_after_start"),
        Index("ix_room_availabilities_room_window", "room_id", "start_time", "end_time"),
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
