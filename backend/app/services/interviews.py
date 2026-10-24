"""Reading one interview: who may see it, and its calendar file."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import Interview, InterviewStatus, User, UserRole
from app.schemas.booking import BookedOut
from app.services.errors import NotFound
from app.services.ics import IcsEvent, render_calendar


def get_interview(db: Session, interview_id: uuid.UUID) -> Interview:
    iv = db.get(Interview, interview_id)
    if iv is None:
        raise NotFound("interview not found")
    return iv


def can_view(user: User, iv: Interview) -> bool:
    if user.role == UserRole.COORDINATOR:
        return True
    if user.role == UserRole.CANDIDATE:
        return iv.candidate_id == user.id
    return any(pa.interviewer_id == user.id and pa.is_active for pa in iv.panel)


def booked_out(iv: Interview) -> BookedOut:
    return BookedOut(
        interview_id=iv.id, stage_id=iv.stage_id, start=iv.start_time, end=iv.end_time,
        status=iv.status, room=iv.room.name if iv.room else None,
        location=iv.room.location if iv.room else None,
    )


def ics_for(iv: Interview) -> str:
    location = ""
    if iv.room:
        location = iv.room.name + (f", {iv.room.location}" if iv.room.location else "")
    event = IcsEvent(
        uid=f"{iv.id}@interviewos",
        start=iv.start_time,
        end=iv.end_time,
        summary=f"{iv.stage.name} interview",
        description=f"{iv.stage.name} round of {iv.stage.drive.title}.",
        location=location,
        sequence=max(iv.version - 1, 0),     # calendars replace the old copy when this goes up
        cancelled=iv.status in (InterviewStatus.CANCELLED, InterviewStatus.NO_SHOW),
    )
    return render_calendar([event])
