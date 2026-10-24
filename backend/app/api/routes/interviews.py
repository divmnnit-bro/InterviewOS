from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models import Notification, NotificationChannel, User
from app.schemas.notification import NotificationOut
from app.services.interviews import can_view, get_interview, ics_for

router = APIRouter(tags=["interviews and notifications"])


@router.get("/interviews/{interview_id}/ics")
def interview_ics(interview_id: uuid.UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)) -> Response:
    iv = get_interview(db, interview_id)
    if not can_view(user, iv):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "interview not found")  # same answer as a missing id
    return Response(ics_for(iv), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="interview.ics"'})


@router.get("/notifications", response_model=list[NotificationOut])
def my_notifications(unread_only: bool = False, limit: int = Query(50, ge=1, le=200),
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Notification]:
    q = select(Notification).where(Notification.user_id == user.id,
                                   Notification.channel == NotificationChannel.IN_APP)
    if unread_only:
        q = q.where(Notification.is_read.is_(False))
    return list(db.scalars(q.order_by(Notification.created_at.desc()).limit(limit)))


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: uuid.UUID, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)) -> Notification:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "notification not found")
    n.is_read = True
    db.commit()
    return n
