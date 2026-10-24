from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models import User, UserRole, UserStatus

_bearer = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise _UNAUTHENTICATED
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise _UNAUTHENTICATED
    user = db.get(User, user_id)
    # Role and status come from the database on every request, not from the token.
    if user is None or user.status != UserStatus.ACTIVE:
        raise _UNAUTHENTICATED
    return user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    allowed = set(roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "you do not have permission to do this")
        return user

    return dependency


require_coordinator = require_roles(UserRole.COORDINATOR)
require_staff = require_roles(UserRole.INTERVIEWER, UserRole.COORDINATOR)
