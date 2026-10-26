from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AIInterviewKit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Generated interview question sets and rubrics for a drive stage."""

    __tablename__ = "ai_interview_kits"

    drive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recruitment_drives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_stages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    creator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False, default="intermediate")
    coding_challenges: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    system_design_scenarios: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    behavioral_questions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    multiple_choice_questions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    competencies_to_assess: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    rubric_template: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    provider_used: Mapped[str] = mapped_column(String(64), nullable=False, default="deterministic")
    model_used: Mapped[str] = mapped_column(String(64), nullable=False, default="local")
    raw_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AIInterviewKit id={self.id} topic={self.topic!r} difficulty={self.difficulty}>"
