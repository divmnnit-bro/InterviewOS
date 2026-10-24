from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.evaluation import Evaluation
    from app.models.panel_assignment import PanelAssignment
    from app.models.user import User


class Interviewer(TimestampMixin, Base):
    """Interviewer profile. Shares its primary key with the owning User.

    `skills` are tags matched against a stage's required skills by the
    scheduler. `capacity` is the maximum number of interviews this person can
    take per day (the workload cap used as a hard constraint in CP-SAT).
    Panel membership goes through `PanelAssignment`.
    """

    __tablename__ = "interviewers"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="capacity_positive"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    skills: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)),
        nullable=False,
        default=list,
        server_default=text("'{}'"),
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    department: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[User] = relationship(back_populates="interviewer")
    panel_assignments: Mapped[list[PanelAssignment]] = relationship(
        back_populates="interviewer"
    )
    evaluations: Mapped[list[Evaluation]] = relationship(back_populates="interviewer")

    def __repr__(self) -> str:
        return f"<Interviewer {self.user_id} skills={self.skills}>"
