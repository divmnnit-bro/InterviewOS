"""Self-booking. A candidate follows a link, sees free slots, and books one.

Safety, in the order a confirmation goes through it:
  1. Idempotency: the client's key is hashed with the candidate id (so one candidate can never read
     another's booking by guessing a key). Same key + same slot = same interview, no second row.
  2. The candidate's enrolment row is locked, so two requests from the same candidate serialise.
  3. The slot is placed, then the chosen interviewers' rows are locked (sorted, so no deadlocks).
  4. Everything is re-read AFTER the locks and the placement is re-checked with the independent
     checker: availability, skills, room, overlaps, rest buffer and daily limits as they are now.
  5. Insert. The database's exclusion constraints are the final guard against a double booking.
Runs under PostgreSQL's default READ COMMITTED isolation, which step 4 relies on: a statement run
after a lock is granted sees everything committed before the lock was granted.
Notifications are created only after the commit and can never fail the booking.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import BookingClaims, create_booking_token
from app.models import (
    AuditEvent,
    DriveCandidate,
    DriveCandidateStatus,
    DriveStatus,
    Interview,
    Interviewer,
    InterviewStatus,
    PanelAssignment,
    RecruitmentDrive,
    User,
    UserStatus,
)
from app.scheduler import booking as pure
from app.schemas.schedule import ProposeOptions
from app.services import notifications
from app.services.errors import (
    Conflict,
    IdempotencyMismatch,
    InvalidLink,
    NotFound,
    SlotUnavailable,
)
from app.services.scheduling import build_schedule_input, get_drive

log = logging.getLogger(__name__)

BOOKABLE = (DriveStatus.COLLECTING_AVAILABILITY, DriveStatus.PUBLISHED, DriveStatus.IN_PROGRESS)
_FIXED = (InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED, InterviewStatus.COMPLETED)
_IDEMPOTENCY_CONSTRAINT = "uq_interviews_idempotency_key"


def db_idempotency_key(candidate_id: uuid.UUID, client_key: str) -> str:
    return hashlib.sha256(f"{candidate_id}:{client_key}".encode()).hexdigest()  # 64 hex chars


@dataclass(frozen=True)
class IssuedLink:
    candidate_id: uuid.UUID
    token: str


# ------------------------------------------------------------------ issuing links


def _target_stage(enrollment: DriveCandidate, drive: RecruitmentDrive) -> uuid.UUID | None:
    stage_ids = [s.id for s in drive.stages]
    if enrollment.current_stage_id and enrollment.current_stage_id in stage_ids:
        return enrollment.current_stage_id
    return stage_ids[0] if stage_ids else None


def issue_links(
    db: Session, drive_id: uuid.UUID, candidate_ids: list[uuid.UUID] | None, ttl_hours: int,
) -> tuple[list[IssuedLink], list[dict]]:
    drive = get_drive(db, drive_id)
    if drive.status not in BOOKABLE:
        raise Conflict(f"drive is {drive.status.value}; candidates cannot book yet")
    if not drive.stages:
        raise Conflict("the drive has no stages")
    q = select(DriveCandidate).where(
        DriveCandidate.drive_id == drive_id, DriveCandidate.status == DriveCandidateStatus.ACTIVE)
    enrollments = {e.candidate_id: e for e in db.scalars(q)}
    wanted = candidate_ids if candidate_ids is not None else list(enrollments)
    fixed = {
        (c, s) for c, s in db.execute(
            select(Interview.candidate_id, Interview.stage_id).where(
                Interview.stage_id.in_([s.id for s in drive.stages]), Interview.status.in_(_FIXED)))
    }
    links: list[IssuedLink] = []
    skipped: list[dict] = []
    for cid in wanted:
        e = enrollments.get(cid)
        stage_id = _target_stage(e, drive) if e else None
        if e is None or stage_id is None:
            skipped.append({"candidate_id": cid, "reason": "not an active candidate of this drive"})
        elif (cid, stage_id) in fixed:
            skipped.append({"candidate_id": cid, "reason": "already has an interview for this round"})
        else:
            links.append(IssuedLink(cid, create_booking_token(
                cid, drive_id, stage_id, ttl=timedelta(hours=ttl_hours))))
    return links, skipped


# ------------------------------------------------------------------ resolving a link


def _resolve(db: Session, claims: BookingClaims) -> tuple[RecruitmentDrive, DriveCandidate]:
    drive = db.get(RecruitmentDrive, claims.drive_id)
    enrollment = db.get(DriveCandidate, (claims.drive_id, claims.candidate_id))
    user = db.get(User, claims.candidate_id)
    # One message for every failure, so a link cannot be used to probe which ids exist.
    if (drive is None or enrollment is None or user is None or user.status != UserStatus.ACTIVE
            or enrollment.status != DriveCandidateStatus.ACTIVE):
        raise InvalidLink("this booking link is not valid")
    if drive.status not in BOOKABLE:
        raise Conflict(f"booking is closed (drive is {drive.status.value})")
    if _target_stage(enrollment, drive) != claims.stage_id:
        raise Conflict("this link is for an earlier round; ask your coordinator for a new one")
    return drive, enrollment


def existing_booking(db: Session, claims: BookingClaims) -> Interview | None:
    return db.scalars(
        select(Interview).where(
            Interview.candidate_id == claims.candidate_id,
            Interview.stage_id == claims.stage_id,
            Interview.status.in_(_FIXED),
        )
    ).first()


def offers_for(
    db: Session, claims: BookingClaims, *, limit: int = 50, after: datetime | None = None,
) -> tuple[RecruitmentDrive, Interview | None, list[pure.Offer]]:
    drive, _ = _resolve(db, claims)
    booked = existing_booking(db, claims)
    if booked is not None:
        return drive, booked, []
    inp = build_schedule_input(db, drive, ProposeOptions(), only_candidate=claims.candidate_id,
                               keep_proposals=True)
    return drive, None, pure.offer_slots(inp, claims.candidate_id, claims.stage_id,
                                         limit=limit, after=after)


# ------------------------------------------------------------------ booking


def _by_key(db: Session, key: str) -> Interview | None:
    return db.scalars(
        select(Interview).where(Interview.idempotency_key == key).execution_options(populate_existing=True)
    ).first()


def _replay(iv: Interview, start: datetime) -> tuple[Interview, bool]:
    if iv.start_time != start:
        raise IdempotencyMismatch("this Idempotency-Key was already used for a different slot")
    return iv, False


def book(
    db: Session, claims: BookingClaims, start: datetime, client_key: str
) -> tuple[Interview, bool]:
    """Book `start`. Returns (interview, created). created=False means an idempotent replay."""
    key = db_idempotency_key(claims.candidate_id, client_key)
    prior = _by_key(db, key)
    if prior is not None:
        return _replay(prior, start)

    drive, _ = _resolve(db, claims)
    try:
        # 2. serialise this candidate
        db.execute(
            select(DriveCandidate).where(
                DriveCandidate.drive_id == claims.drive_id,
                DriveCandidate.candidate_id == claims.candidate_id,
            ).with_for_update().execution_options(populate_existing=True)
        )
        prior = _by_key(db, key)           # a concurrent identical request may have just committed
        if prior is not None:
            db.rollback()
            return _replay(prior, start)
        if existing_booking(db, claims) is not None:
            raise Conflict("you already have an interview booked for this round")

        # 3. choose room and panel, then lock the panel
        db.expire_all()
        inp = build_schedule_input(db, drive, ProposeOptions(), only_candidate=claims.candidate_id,
                                   keep_proposals=True)
        placed = pure.place(inp, claims.candidate_id, claims.stage_id, start)
        if placed is None:
            raise SlotUnavailable("that time is no longer available; please choose another")
        db.execute(
            select(Interviewer.user_id).where(Interviewer.user_id.in_(placed.interviewer_ids))
            .order_by(Interviewer.user_id).with_for_update()
        ).all()

        # 4. re-read everything after the locks and re-check this exact placement
        db.expire_all()
        fresh = build_schedule_input(db, drive, ProposeOptions(), only_candidate=claims.candidate_id,
                                     keep_proposals=True)
        problems = pure.recheck(fresh, placed)
        if problems:
            log.info("booking recheck failed for %s: %s", claims.candidate_id, problems)
            raise SlotUnavailable("that time is no longer available; please choose another",
                                  details=problems)

        # 5. insert (a pending coordinator proposal for this candidate and round is superseded)
        superseded = db.execute(
            delete(Interview).where(
                Interview.candidate_id == claims.candidate_id,
                Interview.stage_id == claims.stage_id,
                Interview.status == InterviewStatus.PROPOSED,
            )
        ).rowcount
        iv = Interview(
            id=uuid.uuid4(), stage_id=claims.stage_id, candidate_id=claims.candidate_id, room_id=placed.room_id,
            start_time=placed.start, end_time=placed.end,
            status=InterviewStatus.CONFIRMED, idempotency_key=key,
        )
        iv.panel = [PanelAssignment(interviewer_id=i, start_time=placed.start, end_time=placed.end,
                                    is_active=True) for i in placed.interviewer_ids]
        db.add(iv)
        db.add(AuditEvent(
            actor_id=claims.candidate_id, action="booking.confirm", entity_type="interview",
            entity_id=iv.id,
            details={"drive_id": str(claims.drive_id), "stage_id": str(claims.stage_id),
                     "start": placed.start.isoformat(), "superseded_proposals": superseded},
        ))
        db.flush()               # exclusion / unique constraints fire here
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if name == _IDEMPOTENCY_CONSTRAINT:
            prior = _by_key(db, key)
            if prior is not None:
                return _replay(prior, start)
        raise SlotUnavailable("that time was just taken; please choose another") from exc
    except Exception:
        db.rollback()
        raise

    notifications.notify_booking_confirmed(db, iv.id)   # after the commit; cannot fail the booking
    return iv, True
