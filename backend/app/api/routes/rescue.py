from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_coordinator
from app.db.database import get_db
from app.models import User
from app.scheduler.rescue import Disruption, Move, Placement
from app.schemas.rescue import (
    DisruptionIn,
    DisruptionOut,
    DroppedOut,
    MoveOut,
    PlacementOut,
    RescueApplyOut,
    RescueApplyRequest,
    RescuePlanOut,
    RescueRequest,
)
from app.schemas.schedule import UnscheduledReasonOut
from app.services import rescue as service

router = APIRouter(prefix="/drives/{drive_id}/rescue", tags=["rescue"],
                   dependencies=[Depends(require_coordinator)])


def _disruptions(items: list[DisruptionIn]) -> list[Disruption]:
    return [Disruption(d.kind, d.resource_id, d.start_time, d.end_time) for d in items]


def _placement(p: Placement) -> PlacementOut:
    return PlacementOut(start_time=p.start, end_time=p.end, room_id=p.room_id,
                        interviewer_ids=list(p.interviewer_ids))


def _move(m: Move) -> MoveOut:
    return MoveOut(
        interview_id=m.interview_id, candidate_id=m.candidate_id, stage_id=m.stage_id,
        old=_placement(m.old), new=_placement(m.new),
        changes=sorted(c.value for c in m.changes),
        directly_affected=m.directly_affected, notifies_candidate=m.notifies_candidate,
    )


def _plan_out(drive_id: uuid.UUID, ctx: service.RescueContext, plan) -> dict:
    return dict(
        drive_id=drive_id,
        schedule_version=ctx.version,
        solver_status=plan.status.value,
        fully_repaired=plan.fully_repaired,
        plan_fingerprint=service.plan_fingerprint(plan),
        disruptions=[
            DisruptionOut(kind=d.kind, resource_id=d.resource_id, start_time=d.start, end_time=d.end,
                          implicit=d in ctx.implicit)
            for d in ctx.disruptions + ctx.implicit
        ],
        affected=list(plan.affected),
        moves=[_move(m) for m in plan.moves],
        collateral_count=len(plan.collateral),
        dropped=[
            DroppedOut(
                interview_id=d.interview_id, candidate_id=d.candidate_id, stage_id=d.stage_id,
                reasons=[UnscheduledReasonOut(code=r.code.value, detail=r.detail) for r in d.reasons])
            for d in plan.dropped
        ],
        needs_manual=list(plan.needs_manual),
        unchanged=list(plan.unchanged),
        candidates_to_notify=list(plan.candidates_to_notify),
        interviewers_to_notify=list(plan.interviewers_to_notify),
    )


# Plain `def` routes: FastAPI runs them in a worker thread, so a slow solve does not block the server.


@router.post("/preview", response_model=RescuePlanOut)
def preview(drive_id: uuid.UUID, body: RescueRequest, db: Session = Depends(get_db)) -> RescuePlanOut:
    """Show what repairing the published schedule would change. Saves nothing.

    Echo `schedule_version` as `expected_version` and `plan_fingerprint` back to `/apply`.
    """
    ctx, plan = service.preview_rescue(db, drive_id, _disruptions(body.disruptions), body.options)
    return RescuePlanOut(**_plan_out(drive_id, ctx, plan))


@router.post("/apply", response_model=RescueApplyOut)
def apply(drive_id: uuid.UUID, body: RescueApplyRequest, db: Session = Depends(get_db),
          user: User = Depends(require_coordinator)) -> RescueApplyOut:
    """Repair the published schedule atomically.

    409 `stale_schedule_version` if the schedule moved on since the preview, `plan_changed` if
    the repair computed now differs from the previewed one (when `plan_fingerprint` is sent),
    and `conflict` if a booking raced the repair. In every 409 case nothing was changed.
    """
    out = service.apply_rescue(
        db, drive_id, user.id, _disruptions(body.disruptions), body.options,
        body.expected_version, body.plan_fingerprint,
    )
    return RescueApplyOut(
        **_plan_out(drive_id, out.ctx, out.plan),
        applied=out.applied, new_schedule_version=out.new_version,
        moved_count=out.moved, cancelled_count=out.cancelled,
        notifications_created=out.notifications,
    )
