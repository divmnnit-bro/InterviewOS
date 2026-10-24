from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.drive_candidate import DriveCandidate
    from app.models.interview import Interview
    from app.models.user import User


class Candidate(TimestampMixin, Base):
    """Candidate profile. Shares its primary key with the owning User.

    Availability windows live in the `Availability` table (owner_id = user_id).
    Drive membership and pipeline progress live in `DriveCandidate`.
    """

    __tablename__ = "candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    roll_number: Mapped[str | None] = mapped_column(String(32), unique=True)
    branch: Mapped[str | None] = mapped_column(String(64))
    cgpa: Mapped[float | None] = mapped_column(Numeric(4, 2))
    resume_url: Mapped[str | None] = mapped_column(String(512))

    user: Mapped[User] = relationship(back_populates="candidate")
    interviews: Mapped[list[Interview]] = relationship(back_populates="candidate")
    enrollments: Mapped[list[DriveCandidate]] = relationship(back_populates="candidate")

    def __repr__(self) -> str:
        return f"<Candidate {self.user_id}>"
