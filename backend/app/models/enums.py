import enum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """SQLAlchemy Enum column type that stores the enum *values* ('cancelled').

    By default SQLAlchemy stores member names ('CANCELLED'). Storing values keeps
    the database labels identical to the API strings, and lets raw SQL (such as
    the WHERE clauses of the exclusion constraints) use the lowercase values.
    """
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda e: [member.value for member in e],
    )


class UserRole(str, enum.Enum):
    CANDIDATE = "candidate"
    INTERVIEWER = "interviewer"
    COORDINATOR = "coordinator"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class DriveStatus(str, enum.Enum):
    DRAFT = "draft"                                    # being configured
    COLLECTING_AVAILABILITY = "collecting_availability"
    PUBLISHED = "published"                            # schedule published
    IN_PROGRESS = "in_progress"                        # interview rounds running
    COMPLETED = "completed"
    ARCHIVED = "archived"


class StageType(str, enum.Enum):
    CODING = "coding"
    TECHNICAL = "technical"
    HR = "hr"


class DriveCandidateStatus(str, enum.Enum):
    ACTIVE = "active"          # still in the pipeline
    REJECTED = "rejected"      # failed a stage
    SELECTED = "selected"      # passed the final stage
    WITHDRAWN = "withdrawn"


class InterviewStatus(str, enum.Enum):
    PROPOSED = "proposed"      # solver output, not yet published
    SCHEDULED = "scheduled"    # published, awaiting candidate confirmation
    CONFIRMED = "confirmed"    # candidate booked / coordinator confirmed
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Recommendation(str, enum.Enum):
    """An interviewer's overall verdict on a candidate for one interview."""

    STRONG_HIRE = "strong_hire"
    HIRE = "hire"
    NO_HIRE = "no_hire"
    STRONG_NO_HIRE = "strong_no_hire"


class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    CALENDAR = "calendar"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
