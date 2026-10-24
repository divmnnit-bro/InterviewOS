"""Conflict explanations and Ripple Rescue, wired to the database.

    explain_schedule   solve a fresh run (nothing saved) and say why anyone was left out
    preview_rescue     compute a repair for a disruption (nothing saved)
    apply_rescue       compute it again and apply it atomically

Rules this module enforces:
  * Previewing never writes. Applying recomputes the plan from the current database state, so the
    coordinator can never apply a stale plan: `expected_version` must match the drive's
    schedule_version, and `plan_fingerprint` (from the preview) must match the plan computed now.
  * The solve runs with no transaction open. The write phase locks the drive row, then checks that
    no interview of the drive was changed, added or removed since the plan was computed.
  * All changes, the audit event and the version bump commit together or not at all. The database's
    exclusion constraints stay the last line of defence against a double booking.
  * Notifications are created after the commit. A failure there is logged and never undoes the repair.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AuditEvent,
    DriveCandidate,
    DriveCandidateStatus,
    DriveStatus,
    Interview,
    Interviewer,
    InterviewStatus,
    Notification,
    NotificationChannel,
    NotificationStatus,
    PanelAssignment,
    RecruitmentDrive,
    Room,
)
from app.scheduler import (
    InterviewerSpec,
    InvalidScheduleInput,
    RoomSpec,
    ScheduleInput,
    ScheduleResult,
    solve,
    validate_input,
)
from app.scheduler.explain import ExplanationReport, explain
from app.scheduler.rescue import CurrentInterview, Disruption, DisruptionKind, RescuePlan, rescue
from app.scheduler.verify import verify
from app.schemas.schedule import ProposeOptions
from app.services import scheduling
from app.services.errors import Conflict, PlanChanged, StaleScheduleVersion, Unprocessable

log = logging.getLogger(__name__)

_PUBLISHED = (InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED)
_REPAIRABLE_DRIVE = (DriveStatus.PUBLISHED, DriveStatus.IN_PROGRESS)
# Interviews being moved are first parked in unique far-future slots so that a chain of moves
# (A takes B's old slot, B takes C's) never trips the exclusion constraints half-way through.
_PARKING_START = datetime(2200, 1, 1, tzinfo=timezone.utc)

RESCHEDULED = "interview_rescheduled"
CANCELLED = "interview_cancelled"
PANEL_CHANGED = "interview_panel_changed"


def _now() -> datetime:
    """The clock the repair uses to decide which interviews have already started. Tests replace it."""
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ explain


def explain_schedule(
    db: Session, drive_id: uuid.UUID, options: ProposeOptions, max_whatifs: int
) -> tuple[int, ScheduleResult, ExplanationReport]:
    """Solve a fresh run for the drive and explain everyone it leaves out. Saves nothing.

    Returns (schedule_version, result, report). The run replaces nothing: the drive's pending
    proposal, if any, is ignored exactly as a new `propose` would ignore it.
    """
    drive = scheduling.get_drive(db, drive_id)
    if drive.status not in scheduling._SCHEDULABLE_DRIVE:
        raise Conflict(f"drive is {drive.status.value}; it cannot be scheduled")
    version = drive.schedule_version
    inp = scheduling.build_schedule_input(db, drive, options)
    db.rollback()  # end the read transaction before the (possibly slow) solve

    try:
        validate_input(inp)
    except InvalidScheduleInput as exc:
        raise Unprocessable("scheduler input is invalid", details=exc.problems) from exc
    result = solve(inp)
    problems = verify(inp, result)
    if problems:
        log.error("explain run for drive %s failed verification: %s", drive_id, problems)
        raise Unprocessable("the solver produced a schedule that failed verification", details=problems)

    report = explain(
        inp, result, max_whatifs=max_whatifs,
        whatif_time_limit=min(5.0, options.time_limit_seconds),
    )
    return version, result, report


# ------------------------------------------------------------------- rescue


@dataclass(frozen=True)
class RescueContext:
    """Plain data read from the database. Holds no ORM objects, so it survives a rollback."""

    version: int
    timezone: str
    inp: ScheduleInput
    current: tuple[CurrentInterview, ...]
    disruptions: tuple[Disruption, ...]       # what the coordinator reported
    implicit: tuple[Disruption, ...]          # added because a booked room/interviewer is unusable
    snapshot: dict[uuid.UUID, tuple[InterviewStatus, int]]   # repairable interview -> (status, version)
    occupying: frozenset[uuid.UUID]           # every interview of the drive holding a slot
    stage_names: dict[uuid.UUID, str]
    room_names: dict[uuid.UUID, str]
    now: datetime


def _whole_horizon(kind: DisruptionKind, resource_id: uuid.UUID, inp: ScheduleInput) -> Disruption:
    return Disruption(kind, resource_id, inp.config.horizon_start, inp.config.horizon_end)


def build_rescue_context(
    db: Session, drive_id: uuid.UUID, disruptions: list[Disruption], options: ProposeOptions
) -> RescueContext:
    """Read the drive's published schedule and everything needed to repair it. Writes nothing."""
    drive = scheduling.get_drive(db, drive_id)
    if drive.status not in _REPAIRABLE_DRIVE:
        raise Conflict(f"drive is {drive.status.value}; there is no published schedule to repair")
    now = _now()
    stage_ids = [s.id for s in drive.stages]

    active = set(db.scalars(
        select(DriveCandidate.candidate_id).where(
            DriveCandidate.drive_id == drive.id,
            DriveCandidate.status == DriveCandidateStatus.ACTIVE,
        )
    ))
    # Interviews without a room or without a panel cannot be described to the solver; they stay
    # where they are and the solver schedules around them. So do those of withdrawn candidates.
    rows = list(db.scalars(
        select(Interview)
        .where(
            Interview.stage_id.in_(stage_ids),
            Interview.status.in_(_PUBLISHED),
            Interview.room_id.is_not(None),
            Interview.candidate_id.in_(active),
        )
        .options(selectinload(Interview.panel))
        .order_by(Interview.start_time, Interview.id)
    ))
    panels = {
        r.id: tuple(sorted((p.interviewer_id for p in r.panel if p.is_active), key=str)) for r in rows
    }
    rows = [r for r in rows if panels[r.id]]
    if not rows:
        raise Conflict("this drive has no published interviews to repair")

    inp = scheduling.build_schedule_input(db, drive, options, keep_proposals=True, rescue_of=rows)
    cfg = inp.config

    # A room that was deactivated, or an interviewer who was suspended, may still hold interviews.
    # They are described to the solver as unusable for the whole drive, and the interviews in them
    # count as directly hit.
    implicit: list[Disruption] = []
    missing_rooms = {r.room_id for r in rows} - {r.id for r in inp.rooms}
    extra_rooms: list[RoomSpec] = []
    if missing_rooms:
        for room in db.scalars(select(Room).where(Room.id.in_(missing_rooms))):
            extra_rooms.append(RoomSpec(id=room.id, capacity=room.capacity, name=room.name, availability=()))
            implicit.append(_whole_horizon(DisruptionKind.ROOM_OUT, room.id, inp))
    missing_ivs = {i for p in panels.values() for i in p} - {i.id for i in inp.interviewers}
    extra_ivs: list[InterviewerSpec] = []
    if missing_ivs:
        for iv in db.scalars(select(Interviewer).where(Interviewer.user_id.in_(missing_ivs))):
            extra_ivs.append(InterviewerSpec(
                id=iv.user_id, skills=frozenset(iv.skills or ()), availability=(),
                capacity_per_day=iv.capacity))
            implicit.append(_whole_horizon(DisruptionKind.INTERVIEWER_OUT, iv.user_id, inp))
    if extra_rooms or extra_ivs:
        inp = replace(inp, rooms=inp.rooms + tuple(extra_rooms),
                      interviewers=inp.interviewers + tuple(extra_ivs))

    # The coordinator may only name a resource the repair knows about. A typo must not look like
    # "nothing was affected".
    rooms_known = {r.id for r in inp.rooms}
    ivs_known = {i.id for i in inp.interviewers}
    cands_known = {c.id for c in inp.candidates}
    for d in disruptions:
        known, noun = {
            DisruptionKind.ROOM_OUT: (rooms_known, "a room"),
            DisruptionKind.INTERVIEWER_OUT: (ivs_known, "an active interviewer"),
            DisruptionKind.CANDIDATE_OUT: (cands_known, "a candidate with a published interview in this drive"),
        }[d.kind]
        if d.resource_id not in known:
            raise Unprocessable(f"{d.resource_id} is not {noun}", details={"kind": d.kind.value})
    reported = {(d.kind, d.resource_id) for d in disruptions}
    implicit = [d for d in implicit if (d.kind, d.resource_id) not in reported]

    slot_seconds = cfg.slot_minutes * 60
    current = tuple(
        CurrentInterview(
            id=r.id, candidate_id=r.candidate_id, stage_id=r.stage_id,
            start=r.start_time, end=r.end_time, room_id=r.room_id, interviewer_ids=panels[r.id],
            # An interview that is off the slot grid or outside the window cannot be re-placed
            # by the solver, so it is fixed in place and reported as needing manual care if hit.
            locked=(
                (r.start_time - cfg.horizon_start).total_seconds() % slot_seconds != 0
                or r.start_time < cfg.horizon_start or r.end_time > cfg.horizon_end
            ),
        )
        for r in rows
    )
    occupying = frozenset(db.scalars(
        select(Interview.id).where(
            Interview.stage_id.in_(stage_ids), Interview.status.in_(scheduling._OCCUPYING)
        )
    ))
    return RescueContext(
        version=drive.schedule_version,
        timezone=drive.timezone,
        inp=inp,
        current=current,
        disruptions=tuple(disruptions),
        implicit=tuple(implicit),
        snapshot={r.id: (r.status, r.version) for r in rows},
        occupying=occupying,
        stage_names={s.id: s.name for s in drive.stages},
        room_names={r.id: r.name for r in inp.rooms},
        now=now,
    )


def compute_plan(ctx: RescueContext) -> RescuePlan:
    """Run the pure repair on a context. May be slow; call it with no transaction open."""
    try:
        plan = rescue(ctx.inp, ctx.current, ctx.disruptions + ctx.implicit, now=ctx.now)
    except InvalidScheduleInput as exc:
        raise Unprocessable("the published schedule cannot be repaired as it stands",
                            details=exc.problems) from exc
    if plan.violations:
        # A solver/checker disagreement is a bug. Never act on it.
        log.error("rescue plan failed verification: %s", plan.violations)
        raise Unprocessable("the repair failed verification, so nothing was changed",
                            details=list(plan.violations))
    return plan


def plan_fingerprint(plan: RescuePlan) -> str:
    """A short digest of what applying `plan` would do. Equal plans have equal fingerprints."""
    def when(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).isoformat()

    doc = {
        "moves": sorted(
            [str(m.interview_id), when(m.new.start), str(m.new.room_id),
             sorted(str(i) for i in m.new.interviewer_ids)]
            for m in plan.moves
        ),
        "dropped": sorted(str(d.interview_id) for d in plan.dropped),
        "manual": sorted(str(i) for i in plan.needs_manual),
    }
    return hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()[:32]


def preview_rescue(
    db: Session, drive_id: uuid.UUID, disruptions: list[Disruption], options: ProposeOptions
) -> tuple[RescueContext, RescuePlan]:
    ctx = build_rescue_context(db, drive_id, disruptions, options)
    db.rollback()  # end the read transaction before the solve
    return ctx, compute_plan(ctx)


@dataclass(frozen=True)
class RescueApplied:
    ctx: RescueContext
    plan: RescuePlan
    applied: bool
    new_version: int
    moved: int
    cancelled: int
    notifications: int


def apply_rescue(
    db: Session,
    drive_id: uuid.UUID,
    actor_id: uuid.UUID,
    disruptions: list[Disruption],
    options: ProposeOptions,
    expected_version: int,
    plan_fingerprint_expected: str | None = None,
) -> RescueApplied:
    """Repair the published schedule. Atomic: every change commits together, or none does.

    Moved interviews are updated in place (same interview id, `version` bumped) and keep their
    status. Interviews that cannot be re-placed are cancelled and free their slot; their
    candidate can book again from a fresh slot list. Interviews that were hit but are locked
    (already started) are left alone and reported in `plan.needs_manual`.
    """
    ctx = build_rescue_context(db, drive_id, disruptions, options)
    db.rollback()
    if ctx.version != expected_version:
        raise StaleScheduleVersion(
            "the schedule changed since this repair was previewed; preview it again",
            details={"expected": expected_version, "current": ctx.version},
        )
    plan = compute_plan(ctx)
    fingerprint = plan_fingerprint(plan)
    if plan_fingerprint_expected is not None and plan_fingerprint_expected != fingerprint:
        raise PlanChanged(
            "the repair computed now differs from the one that was previewed; review it again",
            details={"previewed": plan_fingerprint_expected, "current": fingerprint},
        )

    if not plan.moves and not plan.dropped:
        # Nothing to change (nothing hit, or only locked interviews hit): write nothing.
        return RescueApplied(ctx, plan, False, ctx.version, 0, 0, 0)

    try:
        drive = scheduling._lock_drive(db, drive_id)
        _check_unchanged(db, drive, ctx, expected_version)

        bumped = db.execute(
            update(RecruitmentDrive)
            .where(RecruitmentDrive.id == drive_id, RecruitmentDrive.schedule_version == expected_version)
            .values(schedule_version=expected_version + 1)
        )
        if bumped.rowcount != 1:
            raise StaleScheduleVersion(
                "the schedule changed since this repair was previewed; preview it again",
                details={"expected": expected_version, "current": drive.schedule_version},
            )
        _write_plan(db, plan)
        db.add(AuditEvent(
            actor_id=actor_id,
            action="schedule.rescue",
            entity_type="drive",
            entity_id=drive_id,
            details={
                "from_version": expected_version,
                "to_version": expected_version + 1,
                "plan_fingerprint": fingerprint,
                "disruptions": [
                    {"kind": d.kind.value, "resource_id": str(d.resource_id),
                     "start": d.start.isoformat(), "end": d.end.isoformat(),
                     "implicit": d in ctx.implicit}
                    for d in ctx.disruptions + ctx.implicit
                ],
                "affected": [str(i) for i in plan.affected],
                "moved": [str(m.interview_id) for m in plan.moves],
                "cancelled": [str(d.interview_id) for d in plan.dropped],
                "needs_manual": [str(i) for i in plan.needs_manual],
            },
        ))
        db.flush()  # exclusion constraints fire here
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(
            "a room, interviewer or candidate was booked by someone else while this repair was "
            "being applied; nothing was changed. Preview it again"
        ) from exc
    except Exception:
        db.rollback()
        raise

    created = _notify(db, drive_id, ctx, plan)   # after the commit; cannot undo the repair
    return RescueApplied(ctx, plan, True, expected_version + 1, len(plan.moves), len(plan.dropped), created)


def _check_unchanged(db: Session, drive: RecruitmentDrive, ctx: RescueContext, expected: int) -> None:
    """With the drive locked, confirm nothing the plan relied on has moved since it was computed."""
    stale = StaleScheduleVersion(
        "the schedule changed while this repair was being computed; preview it again",
        details={"expected": expected, "current": drive.schedule_version},
    )
    if drive.schedule_version != expected or drive.schedule_version != ctx.version:
        raise stale
    if drive.status not in _REPAIRABLE_DRIVE:
        raise Conflict(f"drive is {drive.status.value}; there is no published schedule to repair")
    stage_ids = [s.id for s in drive.stages]
    now_occupying = {
        i for i in db.scalars(
            select(Interview.id).where(
                Interview.stage_id.in_(stage_ids), Interview.status.in_(scheduling._OCCUPYING)
            )
        )
    }
    if now_occupying != set(ctx.occupying):
        raise stale  # an interview was booked, cancelled or replaced in the meantime
    locked = db.execute(
        select(Interview.id, Interview.status, Interview.version)
        .where(Interview.id.in_(list(ctx.snapshot)))
        .with_for_update()
    ).all()
    if {i: (s, v) for i, s, v in locked} != ctx.snapshot:
        raise stale


def _write_plan(db: Session, plan: RescuePlan) -> None:
    """Apply moves and cancellations. Runs inside the caller's transaction.

    Order matters because the exclusion constraints are checked after every statement:
      1. free the interviewers being removed and those of cancelled interviews,
      2. park every moved interview in its own unique far-future slot (panel rows follow through
         the composite foreign key's ON UPDATE CASCADE),
      3. cancel the dropped interviews,
      4. move each interview to its final slot,
      5. add the new panel members.
    """
    cancel_ids = [d.interview_id for d in plan.dropped]
    removed: list[tuple[uuid.UUID, uuid.UUID]] = []
    added: list[tuple[uuid.UUID, uuid.UUID, datetime, datetime]] = []
    for m in plan.moves:
        old, new = set(m.old.interviewer_ids), set(m.new.interviewer_ids)
        removed += [(m.interview_id, i) for i in old - new]
        added += [(m.interview_id, i, m.new.start, m.new.end) for i in new - old]

    for interview_id, interviewer_id in removed:
        db.execute(
            update(PanelAssignment)
            .where(PanelAssignment.interview_id == interview_id,
                   PanelAssignment.interviewer_id == interviewer_id)
            .values(is_active=False)
        )
    if cancel_ids:
        db.execute(
            update(PanelAssignment).where(PanelAssignment.interview_id.in_(cancel_ids))
            .values(is_active=False)
        )

    for n, m in enumerate(plan.moves):
        park = _PARKING_START + timedelta(days=n)
        db.execute(
            update(Interview).where(Interview.id == m.interview_id)
            .values(start_time=park, end_time=park + (m.old.end - m.old.start))
        )
    if cancel_ids:
        db.execute(
            update(Interview).where(Interview.id.in_(cancel_ids))
            .values(status=InterviewStatus.CANCELLED, version=Interview.version + 1)
        )
    for m in plan.moves:
        db.execute(
            update(Interview).where(Interview.id == m.interview_id)
            .values(start_time=m.new.start, end_time=m.new.end, room_id=m.new.room_id,
                    version=Interview.version + 1)
        )

    for interview_id, interviewer_id, start, end in added:
        revived = db.execute(
            update(PanelAssignment)
            .where(PanelAssignment.interview_id == interview_id,
                   PanelAssignment.interviewer_id == interviewer_id)
            .values(is_active=True)
        )
        if revived.rowcount == 0:
            db.execute(insert(PanelAssignment).values(
                interview_id=interview_id, interviewer_id=interviewer_id,
                start_time=start, end_time=end, is_active=True))


# -------------------------------------------------------------- notifications


def _notify(db: Session, drive_id: uuid.UUID, ctx: RescueContext, plan: RescuePlan) -> int:
    """Tell everyone a repair touched. Returns how many notifications were created."""
    try:
        tz = ZoneInfo(ctx.timezone)

        def fmt(dt: datetime) -> str:
            return dt.astimezone(tz).strftime("%a %d %b %Y, %H:%M")

        def room(room_id: uuid.UUID) -> str:
            return ctx.room_names.get(room_id, "to be announced")

        rows: list[tuple[uuid.UUID, str, str, str, dict]] = []
        for m in plan.moves:
            stage = ctx.stage_names.get(m.stage_id, "interview")
            payload = {"interview_id": str(m.interview_id), "drive_id": str(drive_id),
                       "old_start": m.old.start.isoformat(), "new_start": m.new.start.isoformat()}
            old_panel, new_panel = set(m.old.interviewer_ids), set(m.new.interviewer_ids)
            if m.notifies_candidate:
                rows.append((m.candidate_id, RESCHEDULED, "Interview rescheduled",
                             f"Your {stage} interview moved from {fmt(m.old.start)} to {fmt(m.new.start)} "
                             f"({tz.key}), room: {room(m.new.room_id)}.", payload))
                for iid in old_panel & new_panel:
                    rows.append((iid, RESCHEDULED, "Interview rescheduled",
                                 f"The {stage} interview you sit on moved from {fmt(m.old.start)} to "
                                 f"{fmt(m.new.start)} ({tz.key}), room: {room(m.new.room_id)}.", payload))
            for iid in new_panel - old_panel:
                rows.append((iid, PANEL_CHANGED, "New interview on your calendar",
                             f"You are on the panel for a {stage} interview on {fmt(m.new.start)} "
                             f"({tz.key}), room: {room(m.new.room_id)}.", payload))
            for iid in old_panel - new_panel:
                rows.append((iid, PANEL_CHANGED, "Removed from an interview",
                             f"You are no longer on the panel for the {stage} interview that was on "
                             f"{fmt(m.old.start)} ({tz.key}).", payload))
        for d in plan.dropped:
            stage = ctx.stage_names.get(d.stage_id, "interview")
            old = next(c for c in ctx.current if c.id == d.interview_id)
            payload = {"interview_id": str(d.interview_id), "drive_id": str(drive_id),
                       "old_start": old.start.isoformat()}
            rows.append((d.candidate_id, CANCELLED, "Interview cancelled",
                         f"Your {stage} interview on {fmt(old.start)} ({tz.key}) had to be cancelled. "
                         "Your coordinator will help you book a new time.", payload))
            for iid in old.interviewer_ids:
                rows.append((iid, CANCELLED, "Interview cancelled",
                             f"The {stage} interview on {fmt(old.start)} ({tz.key}) was cancelled.", payload))

        now = datetime.now(timezone.utc)
        for user_id, kind, title, message, payload in rows:
            db.add(Notification(
                user_id=user_id, type=kind, title=title, message=message, payload=payload,
                channel=NotificationChannel.IN_APP, status=NotificationStatus.SENT,
                attempts=1, sent_at=now,
            ))
        db.commit()
        return len(rows)
    except Exception:
        db.rollback()
        log.exception("could not create rescue notifications for drive %s (the repair stands)", drive_id)
        return 0
