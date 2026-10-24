from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import DriveCandidateStatus, pg_enum
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.drive import RecruitmentDrive
    from app.models.stage import InterviewStage


class DriveCandidate(TimestampMixin, Base):
    """A candidate's enrolment in one drive, and where they are in its pipeline.

    Not in the original class diagram, but needed: a drive has to know which
    candidates it contains, and pass/fail progression has to be tracked per
    candidate per drive.
    """

    __tablename__ = "drive_candidates"

    drive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recruitment_drives.id", ondelete="CASCADE"),
        primary_key=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.user_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    status: Mapped[DriveCandidateStatus] = mapped_column(
        pg_enum(DriveCandidateStatus, "drive_candidate_status"),
        default=DriveCandidateStatus.ACTIVE,
        nullable=False,
    )
    current_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interview_stages.id", ondelete="SET NULL")
    )

    drive: Mapped[RecruitmentDrive] = relationship(back_populates="enrollments")
    candidate: Mapped[Candidate] = relationship(back_populates="enrollments")
    current_stage: Mapped[InterviewStage | None] = relationship()

    def __repr__(self) -> str:
        return f"<DriveCandidate drive={self.drive_id} candidate={self.candidate_id}>"
