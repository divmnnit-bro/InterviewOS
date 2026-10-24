"""Import every model here so Alembic autogenerate and Base.metadata see them all.

Usage in alembic/env.py:  from app.db.base import Base  # noqa
"""

from app.db.database import Base  # noqa: F401
from app.models import (  # noqa: F401
    AuditEvent,
    Availability,
    Candidate,
    DriveCandidate,
    Evaluation,
    Interview,
    InterviewStage,
    Interviewer,
    Notification,
    PanelAssignment,
    RecruitmentDrive,
    Room,
    RoomAvailability,
    User,
)
