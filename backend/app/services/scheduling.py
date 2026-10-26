"""Glue between the database and the pure scheduler.

    build_schedule_input   rows -> ScheduleInput          (reads only)
    propose_schedule       solve, verify, save as PROPOSED (replaces the old proposal)
    publish_schedule       compare-and-swap schedule_version, PROPOSED -> SCHEDULED

Rules this module enforces:
  * A proposal is saved only if the independent checker (`verify`) finds no violations.
  * Saving and publishing both lock the drive row and check `schedule_version`, so a
    proposal built against an old schedule is rejected instead of overwriting newer work.
  * The database's exclusion constraints stay the last line of defence: if two drives
    race for the same room or interviewer, one insert fails and we report a conflict.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, false, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Availability,
    AuditEvent,
    DriveCandidate,
    DriveCandidateStatus,
    DriveStatus,
    Interview,
    Interviewer,
    InterviewStage,
    InterviewStatus,
    PanelAssignment,
    RecruitmentDrive,
    Room,
    RoomAvailability,
    User,
    UserStatus,
)
from app.scheduler import (
    CandidateSpec,
    ExistingBooking,
    InterviewerSpec,
    InvalidScheduleInput,
    RoomSpec,
    ScheduleInput,
    ScheduleResult,
    SchedulerConfig,
    StageSpec,
    Window,
    solve,
    validate_input,
)
from app.scheduler.verify import verify
from app.services.errors import Conflict, NotFound, StaleScheduleVersion, Unprocessable
from app.schemas.schedule import ProposeOptions

log = logging.getLogger(__name__)

# Interviews that are published or done: they are fixed facts the solver must schedule around.
_FIXED = (InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED, InterviewStatus.COMPLETED)
# Anything that still occupies its slot (matches the exclusion constraints' WHERE clause).
_OCCUPYING = (
    InterviewStatus.PROPOSED, InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED,
    InterviewStatus.COMPLETED,
)
_SCHEDULABLE_DRIVE = (
    DriveStatus.DRAFT, DriveStatus.COLLECTING_AVAILABILITY, DriveStatus.PUBLISHED,
    DriveStatus.IN_PROGRESS,
)


# ------------------------------------------------------------------ reading


def get_drive(db: Session, drive_id: uuid.UUID) -> RecruitmentDrive:
    drive = db.get(RecruitmentDrive, drive_id)
    if drive is None:
        raise NotFound("drive not found")
    return drive


def _windows_by_owner(rows, key: str) -> dict[uuid.UUID, tuple[Window, ...]]:
    grouped: dict[uuid.UUID, list[Window]] = defaultdict(list)
    for r in rows:
        grouped[getattr(r, key)].append(Window(r.start_time, r.end_time))
    return {k: tuple(v) for k, v in grouped.items()}


def build_schedule_input(
    db: Session, drive: RecruitmentDrive, options: ProposeOptions | None = None,
    *, only_candidate: uuid.UUID | None = None, keep_proposals: bool = False,
    rescue_of: Sequence[Interview] | None = None,
) -> ScheduleInput:
    """Read everything the solver needs. Nothing is written.

    only_candidate  restrict the run to one candidate (self-booking).
    keep_proposals  treat the drive's pending proposal as occupying its slots (self-booking must
                    not take a slot the coordinator is about to publish). The booking candidate's
                    own pending interview is still ignored, since booking supersedes it.
    rescue_of       the published interviews being repaired (see services/rescue.py). Their
                    candidates are included for the stages those interviews are in, even though
                    they are already booked, and the interviews themselves are left out of the
                    existing bookings because the repair re-places them.
    """
    options = options or ProposeOptions()
    h0, h1 = drive.window_start, drive.window_end

    stages = list(drive.stages)  # ordered by order_index
    if not stages:
        raise Unprocessable("the drive has no stages")
    stage_ids = [s.id for s in stages]
    stage_specs = tuple(
        StageSpec(
            id=s.id,
            order_index=s.order_index,
            duration_minutes=s.duration_minutes,
            panel_size=s.panel_size,
            required_skills=frozenset(s.required_skills or ()),
            name=s.name,
        )
        for s in stages
    )

    # Candidates still in the pipeline, with the round they need next.
    enrollments = db.scalars(
        select(DriveCandidate).where(
            DriveCandidate.drive_id == drive.id,
            DriveCandidate.status == DriveCandidateStatus.ACTIVE,
            *([DriveCandidate.candidate_id == only_candidate] if only_candidate else []),
            *([DriveCandidate.candidate_id.in_({i.candidate_id for i in rescue_of})]
              if rescue_of is not None else []),
        )
    ).all()
    cand_ids = [e.candidate_id for e in enrollments]

    # This drive's interviews that fix a candidate's position: published ones, and completed ones.
    own = db.scalars(
        select(Interview).where(
            Interview.stage_id.in_(stage_ids), Interview.status.in_(_FIXED)
        )
    ).all()
    booked: set[tuple[uuid.UUID, uuid.UUID]] = {(i.candidate_id, i.stage_id) for i in own}
    last_end: dict[uuid.UUID, datetime] = {}
    for i in own:
        if i.status == InterviewStatus.COMPLETED:
            last_end[i.candidate_id] = max(last_end.get(i.candidate_id, i.end_time), i.end_time)

    cand_windows = _windows_by_owner(
        db.scalars(
            select(Availability).where(
                Availability.owner_id.in_(cand_ids),
                Availability.end_time > h0,
                Availability.start_time < h1,
            )
        ).all() if cand_ids else [],
        "owner_id",
    )
    rescue_stage = {i.candidate_id: i.stage_id for i in rescue_of or ()}
    candidates: list[CandidateSpec] = []
    for e in enrollments:
        if rescue_of is not None:
            target = rescue_stage[e.candidate_id]
        else:
            target = e.current_stage_id or stages[0].id
            if target not in stage_ids or (e.candidate_id, target) in booked:
                continue  # already has this round, or points at a stage of another drive
        candidates.append(
            CandidateSpec(
                id=e.candidate_id,
                stage_ids=(target,),
                availability=cand_windows.get(e.candidate_id, ()),
                not_before=last_end.get(e.candidate_id),
            )
        )

    # Interviewers and rooms are shared across drives.
    interviewers = db.scalars(
        select(Interviewer).join(User, User.id == Interviewer.user_id).where(
            User.status == UserStatus.ACTIVE
        )
    ).all()
    iv_windows = _windows_by_owner(
        db.scalars(
            select(Availability).where(
                Availability.owner_id.in_([i.user_id for i in interviewers]),
                Availability.end_time > h0,
                Availability.start_time < h1,
            )
        ).all() if interviewers else [],
        "owner_id",
    )
    interviewer_specs = tuple(
        InterviewerSpec(
            id=i.user_id,
            skills=frozenset(i.skills or ()),
            availability=iv_windows.get(i.user_id, ()),
            capacity_per_day=i.capacity,
        )
        for i in interviewers
    )

    rooms = db.scalars(select(Room).where(Room.is_active.is_(True))).all()
    room_windows = _windows_by_owner(
        db.scalars(
            select(RoomAvailability).where(
                RoomAvailability.room_id.in_([r.id for r in rooms]),
                RoomAvailability.end_time > h0,
                RoomAvailability.start_time < h1,
            )
        ).all() if rooms else [],
        "room_id",
    )
    # Windows that exist but fall outside the horizon must still close the room,
    # so "has any windows at all" is decided separately from "has windows in range".
    restricted = set(
        db.scalars(
            select(RoomAvailability.room_id).where(
                RoomAvailability.room_id.in_([r.id for r in rooms])
            ).distinct()
        ).all()
    ) if rooms else set()
    room_specs = tuple(
        RoomSpec(
            id=r.id,
            capacity=r.capacity,
            name=r.name,
            availability=(room_windows.get(r.id, ()) if r.id in restricted else None),
        )
        for r in rooms
    )

    # Everything already occupying a slot in the horizon, across ALL drives, except this
    # drive's own pending proposal (which this run replaces).
    own_proposed = Interview.stage_id.in_(stage_ids) & (Interview.status == InterviewStatus.PROPOSED)
    if keep_proposals:
        own_proposed = own_proposed & (Interview.candidate_id == only_candidate) if only_candidate \
            else false()
    busy = db.scalars(
        select(Interview).where(
            Interview.status.in_(_OCCUPYING),
            ~own_proposed,
            *([Interview.id.notin_([i.id for i in rescue_of])] if rescue_of else []),
            Interview.end_time > h0,
            Interview.start_time < h1,
        )
    ).all()
    panel: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    if busy:
        for pa in db.scalars(
            select(PanelAssignment).where(
                PanelAssignment.interview_id.in_([b.id for b in busy]),
                PanelAssignment.is_active.is_(True),
            )
        ):
            panel[pa.interview_id].append(pa.interviewer_id)
    existing = tuple(
        ExistingBooking(
            start=b.start_time,
            end=b.end_time,
            candidate_id=b.candidate_id,
            room_id=b.room_id,
            interviewer_ids=tuple(panel.get(b.id, ())),
        )
        for b in busy
    )

    from app.scheduler.types import Weights
    w_kwargs = {}
    if getattr(options, "earliness_weight", None) is not None:
        w_kwargs["earliness"] = options.earliness_weight
    if getattr(options, "load_balance_weight", None) is not None:
        w_kwargs["load_balance"] = options.load_balance_weight
    if getattr(options, "room_fit_weight", None) is not None:
        w_kwargs["room_fit"] = options.room_fit_weight
    weights = Weights(**w_kwargs) if w_kwargs else Weights()

    config = SchedulerConfig(
        horizon_start=h0,
        horizon_end=h1,
        slot_minutes=options.slot_minutes or drive.slot_minutes,
        timezone=drive.timezone,
        interviewer_buffer_minutes=(
            drive.interviewer_buffer_minutes if options.interviewer_buffer_minutes is None
            else options.interviewer_buffer_minutes),
        min_round_gap_minutes=(
            drive.min_round_gap_minutes if options.min_round_gap_minutes is None
            else options.min_round_gap_minutes),
        weights=weights,
        time_limit_seconds=min(options.time_limit_seconds, settings.SCHEDULER_MAX_TIME_LIMIT_SECONDS),
        workers=min(options.workers, settings.SCHEDULER_MAX_WORKERS),
    )
    return ScheduleInput(
        stages=stage_specs,
        candidates=tuple(candidates),
        interviewers=interviewer_specs,
        rooms=room_specs,
        config=config,
        existing=existing,
    )


# ------------------------------------------------------------------ proposing


def _lock_drive(db: Session, drive_id: uuid.UUID) -> RecruitmentDrive:
    """Lock the drive row and refresh it, so the version we compare is the committed one."""
    drive = db.execute(
        select(RecruitmentDrive)
        .where(RecruitmentDrive.id == drive_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if drive is None:
        raise NotFound("drive not found")
    return drive


def propose_schedule(
    db: Session, drive_id: uuid.UUID, actor_id: uuid.UUID, options: ProposeOptions | None = None
) -> tuple[ScheduleInput, ScheduleResult, int]:
    """Solve and save the result as a PROPOSED schedule. Returns (input, result, version).

    The solve runs with no transaction open, so a slow solve never holds locks.
    """
    options = options or ProposeOptions()
    drive = get_drive(db, drive_id)
    if drive.status not in _SCHEDULABLE_DRIVE:
        raise Conflict(f"drive is {drive.status.value}; it cannot be scheduled")
    version = drive.schedule_version

    inp = build_schedule_input(db, drive, options)
    db.rollback()  # end the read transaction before the (possibly slow) solve

    try:
        validate_input(inp)
    except InvalidScheduleInput as exc:
        raise Unprocessable("scheduler input is invalid", details=exc.problems) from exc

    result = solve(inp)

    problems = verify(inp, result)
    if problems:
        # A solver/checker disagreement is a bug. Never save it, and say so loudly.
        log.error("proposal for drive %s failed verification: %s", drive_id, problems)
        raise Unprocessable("the solver produced a schedule that failed verification", details=problems)

    _save_proposal(db, drive_id, actor_id, version, result)
    return inp, result, version


def _save_proposal(
    db: Session, drive_id: uuid.UUID, actor_id: uuid.UUID, expected_version: int,
    result: ScheduleResult,
) -> None:
    try:
        drive = _lock_drive(db, drive_id)
        if drive.schedule_version != expected_version:
            raise StaleScheduleVersion(
                "the schedule changed while this proposal was being built; run it again",
                details={"expected": expected_version, "current": drive.schedule_version},
            )
        stage_ids = [s.id for s in drive.stages]

        # Replace the previous proposal. Bulk delete runs now, so its slots are free before
        # the new rows are inserted. Panel rows go with them (ON DELETE CASCADE).
        db.execute(
            delete(Interview).where(
                Interview.stage_id.in_(stage_ids), Interview.status == InterviewStatus.PROPOSED
            )
        )
        for p in result.interviews:
            iv = Interview(
                stage_id=p.stage_id,
                candidate_id=p.candidate_id,
                room_id=p.room_id,
                start_time=p.start,
                end_time=p.end,
                status=InterviewStatus.PROPOSED,
            )
            iv.panel = [
                PanelAssignment(
                    interviewer_id=iid, start_time=p.start, end_time=p.end, is_active=True
                )
                for iid in p.interviewer_ids
            ]
            db.add(iv)
        db.add(
            AuditEvent(
                actor_id=actor_id,
                action="schedule.propose",
                entity_type="drive",
                entity_id=drive_id,
                details={
                    "based_on_version": expected_version,
                    "solver_status": result.status.value,
                    "interviews": len(result.interviews),
                    "unscheduled": len(result.unscheduled),
                },
            )
        )
        db.flush()  # exclusion constraints fire here
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(
            "a room, interviewer or candidate was booked by someone else while this proposal "
            "was being built; run it again"
        ) from exc
    except Exception:
        db.rollback()
        raise


def get_proposal(db: Session, drive_id: uuid.UUID) -> tuple[int, list[Interview]]:
    drive = get_drive(db, drive_id)
    stage_ids = [s.id for s in drive.stages]
    rows = db.scalars(
        select(Interview)
        .where(Interview.stage_id.in_(stage_ids), Interview.status == InterviewStatus.PROPOSED)
        .order_by(Interview.start_time)
    ).all()
    return drive.schedule_version, list(rows)


def discard_proposal(db: Session, drive_id: uuid.UUID, actor_id: uuid.UUID) -> int:
    try:
        drive = _lock_drive(db, drive_id)
        res = db.execute(
            delete(Interview).where(
                Interview.stage_id.in_([s.id for s in drive.stages]),
                Interview.status == InterviewStatus.PROPOSED,
            )
        )
        db.add(AuditEvent(actor_id=actor_id, action="schedule.discard", entity_type="drive",
                          entity_id=drive_id, details={"removed": res.rowcount}))
        db.commit()
        return res.rowcount
    except Exception:
        db.rollback()
        raise


# ------------------------------------------------------------------ publishing


def publish_schedule(
    db: Session, drive_id: uuid.UUID, actor_id: uuid.UUID, expected_version: int
) -> tuple[int, int, int]:
    """Publish the pending proposal. Returns (new_version, published, superseded_dropped).

    The version bump is a compare-and-swap: it succeeds only if the drive is still at
    `expected_version`, the version the proposal was shown at.
    """
    try:
        drive = _lock_drive(db, drive_id)
        if drive.status not in _SCHEDULABLE_DRIVE:
            raise Conflict(f"drive is {drive.status.value}; nothing can be published")

        swapped = db.execute(
            update(RecruitmentDrive)
            .where(
                RecruitmentDrive.id == drive_id,
                RecruitmentDrive.schedule_version == expected_version,
            )
            .values(schedule_version=expected_version + 1)
        )
        if swapped.rowcount != 1:
            raise StaleScheduleVersion(
                "the schedule changed since this proposal was made; review the new state and retry",
                details={"expected": expected_version, "current": drive.schedule_version},
            )

        stage_ids = [s.id for s in drive.stages]
        pending = db.scalars(
            select(Interview).where(
                Interview.stage_id.in_(stage_ids), Interview.status == InterviewStatus.PROPOSED
            )
        ).all()
        # A candidate who self-booked after the proposal was made must not get a second interview.
        fixed = {
            (c, s) for c, s in db.execute(
                select(Interview.candidate_id, Interview.stage_id).where(
                    Interview.stage_id.in_(stage_ids), Interview.status.in_(_FIXED)))
        }
        superseded = [iv for iv in pending if (iv.candidate_id, iv.stage_id) in fixed]
        for iv in superseded:
            db.delete(iv)
        pending = [iv for iv in pending if (iv.candidate_id, iv.stage_id) not in fixed]
        if not pending:
            raise Conflict("there is no proposal to publish")
        for iv in pending:
            iv.status = InterviewStatus.SCHEDULED  # ORM bumps Interview.version

        if drive.status in (DriveStatus.DRAFT, DriveStatus.COLLECTING_AVAILABILITY):
            db.execute(
                update(RecruitmentDrive)
                .where(RecruitmentDrive.id == drive_id)
                .values(status=DriveStatus.PUBLISHED)
            )
        db.add(
            AuditEvent(
                actor_id=actor_id,
                action="schedule.publish",
                entity_type="drive",
                entity_id=drive_id,
                details={
                    "from_version": expected_version,
                    "to_version": expected_version + 1,
                    "interviews": len(pending),
                    "superseded_dropped": len(superseded),
                    "interview_ids": [str(i.id) for i in pending],
                },
            )
        )
        db.commit()
        return expected_version + 1, len(pending), len(superseded)
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("a slot in this proposal is no longer free; run the proposal again") from exc
    except Exception:
        db.rollback()
        raise


def interviewer_ids_of(db: Session, interviews: list[Interview]) -> dict[uuid.UUID, list[uuid.UUID]]:
    if not interviews:
        return {}
    out: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for pa in db.scalars(
        select(PanelAssignment).where(
            PanelAssignment.interview_id.in_([i.id for i in interviews]),
            PanelAssignment.is_active.is_(True),
        )
    ):
        out[pa.interview_id].append(pa.interviewer_id)
    return out
