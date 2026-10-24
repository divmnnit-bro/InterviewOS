from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import UserRole, UserStatus, pg_enum
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.interviewer import Interviewer


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Identity for a candidate, interviewer, or coordinator."""

    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), nullable=False, index=True
    )
    status: Mapped[UserStatus] = mapped_column(
        pg_enum(UserStatus, "user_status"),
        default=UserStatus.ACTIVE,
        nullable=False,
    )

    # Role-specific profiles (at most one, matching `role`).
    candidate: Mapped[Candidate | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    interviewer: Mapped[Interviewer | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"
