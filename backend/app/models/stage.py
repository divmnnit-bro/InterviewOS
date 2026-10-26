from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import StageType, pg_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.drive import RecruitmentDrive
    from app.models.interview import Interview

# Default progression rule: a candidate advances if their average score is at
# least `min_score`. Stored as JSON so new rule types can be added without a
# schema change; the pipeline service interprets `type`.
DEFAULT_PASS_RULE: dict[str, Any] = {"type": "min_score", "min_score": 6.0}


class InterviewStage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One round of a drive (Coding, Technical or HR). Rounds run in `order_index` order.

    The room a session needs is derived by the scheduler as panel_size + 1
    (the panel plus the candidate), so it is not stored separately.
    """

    __tablename__ = "interview_stages"
    __table_args__ = (
        CheckConstraint("order_index >= 1", name="order_positive"),
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("panel_size > 0", name="panel_size_positive"),
        UniqueConstraint("drive_id", "order_index", name="uq_interview_stages_drive_order"),
        UniqueConstraint("drive_id", "name", name="uq_interview_stages_drive_name"),
    )

    drive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recruitment_drives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    stage_type: Mapped[StageType] = mapped_column(
        pg_enum(StageType, "stage_type"), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    panel_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    required_skills: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)), nullable=False, default=list, server_default=text("'{}'")
    )
    rule: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=lambda: dict(DEFAULT_PASS_RULE)
    )
    rubric_template: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    drive: Mapped[RecruitmentDrive] = relationship(back_populates="stages")
    interviews: Mapped[list[Interview]] = relationship(back_populates="stage")

    def __repr__(self) -> str:
        return f"<InterviewStage #{self.order_index} {self.name!r}>"
