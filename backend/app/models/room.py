from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.interview import Interview


class Room(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A physical or virtual room. Must be large enough for the session."""

    __tablename__ = "rooms"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="capacity_positive"),
    )

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str | None] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    interviews: Mapped[list[Interview]] = relationship(back_populates="room")

    def __repr__(self) -> str:
        return f"<Room {self.name} cap={self.capacity}>"
