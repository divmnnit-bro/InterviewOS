from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole, UserStatus
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterCandidateRequest(BaseModel):
    """Public self-registration. Always creates a candidate; other roles are
    created by a coordinator through POST /users."""

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=1024)
    roll_number: str | None = Field(default=None, max_length=32)
    branch: str | None = Field(default=None, max_length=64)


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=1024)
    role: UserRole
    # interviewer profile (ignored for other roles)
    skills: list[str] = Field(default_factory=list, max_length=50)
    capacity: int = Field(default=4, ge=1, le=50)
    department: str | None = Field(default=None, max_length=64)
    # candidate profile (ignored for other roles)
    roll_number: str | None = Field(default=None, max_length=32)
    branch: str | None = Field(default=None, max_length=64)


class UserOut(ORMModel):
    id: uuid.UUID
    name: str
    email: str
    role: UserRole
    status: UserStatus


class UserDetailOut(ORMModel):
    id: uuid.UUID
    name: str
    email: str
    role: UserRole
    status: UserStatus
    skills: list[str] = Field(default_factory=list)
    capacity: int | None = None
    department: str | None = None
    roll_number: str | None = None
    branch: str | None = None
