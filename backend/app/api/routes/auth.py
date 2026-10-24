from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_coordinator
from app.core.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.models import Candidate, Interviewer, User, UserRole, UserStatus
from app.schemas.auth import (
    CreateUserRequest,
    LoginRequest,
    RegisterCandidateRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(tags=["auth"])


def _create_user(db: Session, data: CreateUserRequest) -> User:
    user = User(
        name=data.name.strip(),
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        role=data.role,
        status=UserStatus.ACTIVE,
    )
    if data.role == UserRole.INTERVIEWER:
        user.interviewer = Interviewer(
            skills=sorted({s.strip() for s in data.skills if s.strip()}),
            capacity=data.capacity,
            department=data.department,
        )
    elif data.role == UserRole.CANDIDATE:
        user.candidate = Candidate(roll_number=data.roll_number, branch=data.branch)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Covers a duplicate email or roll number without saying which exists.
        raise HTTPException(status.HTTP_409_CONFLICT, "that email or roll number is already registered")
    return user


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Always run one scrypt verification so timing does not reveal whether the email exists.
    ok = verify_password(body.password, user.hashed_password if user else DUMMY_HASH)
    if user is None or not ok or user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "incorrect email or password")
    return TokenResponse(access_token=create_access_token(user.id, user.role.value))


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_candidate(body: RegisterCandidateRequest, db: Session = Depends(get_db)) -> User:
    """Public sign-up. Always creates a candidate; it can never create a coordinator."""
    return _create_user(
        db,
        CreateUserRequest(
            name=body.name, email=body.email, password=body.password,
            role=UserRole.CANDIDATE, roll_number=body.roll_number, branch=body.branch,
        ),
    )


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post(
    "/users", response_model=UserOut, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_coordinator)],
)
def create_user(body: CreateUserRequest, db: Session = Depends(get_db)) -> User:
    """Coordinator-only: create an interviewer, candidate or another coordinator."""
    return _create_user(db, body)
