from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_coordinator
from app.db.database import get_db
from app.models import User
from app.schemas.schedule import (
    ProposalOut,
    ProposedInterviewOut,
    ProposeOptions,
    PublishOut,
    PublishRequest,
    UnscheduledOut,
    UnscheduledReasonOut,
)
from app.schemas.rescue import (
    BlockerOut,
    ExplainOut,
    ExplainRequest,
    ExplanationOut,
    FixOut,
    PlacedInterviewOut,
    RescuedKeyOut,
    WhatIfOut,
)
from app.services import rescue as rescue_service
from app.services import scheduling

router = APIRouter(prefix="/drives/{drive_id}/schedule", tags=["schedule"],
                   dependencies=[Depends(require_coordinator)])


def _interview_out(iv, panel: dict) -> ProposedInterviewOut:
    return ProposedInterviewOut(
        id=iv.id, candidate_id=iv.candidate_id, stage_id=iv.stage_id, room_id=iv.room_id,
        start_time=iv.start_time, end_time=iv.end_time, status=iv.status,
        interviewer_ids=sorted(panel.get(iv.id, []), key=str),
    )


# Plain `def` routes: FastAPI runs them in a worker thread, so a slow solve does not block the server.


@router.post("/propose", response_model=ProposalOut)
def propose(drive_id: uuid.UUID, options: ProposeOptions | None = None,
            db: Session = Depends(get_db), user: User = Depends(require_coordinator)) -> ProposalOut:
    """Run the solver, check the result, and save it as the drive's pending proposal.

    Replaces any earlier pending proposal. Nothing is visible to candidates until it is published.
    """
    _, result, version = scheduling.propose_schedule(db, drive_id, user.id, options)
    _, rows = scheduling.get_proposal(db, drive_id)
    panel = scheduling.interviewer_ids_of(db, rows)
    return ProposalOut(
        drive_id=drive_id,
        schedule_version=version,
        solver_status=result.status.value,
        complete=result.complete,
        interviews=[_interview_out(r, panel) for r in rows],
        unscheduled=[
            UnscheduledOut(
                candidate_id=u.candidate_id, stage_id=u.stage_id,
                reasons=[UnscheduledReasonOut(code=r.code.value, detail=r.detail) for r in u.reasons],
            )
            for u in result.unscheduled
        ],
    )


@router.get("/proposal", response_model=ProposalOut)
def current_proposal(drive_id: uuid.UUID, db: Session = Depends(get_db)) -> ProposalOut:
    version, rows = scheduling.get_proposal(db, drive_id)
    panel = scheduling.interviewer_ids_of(db, rows)
    return ProposalOut(drive_id=drive_id, schedule_version=version,
                       interviews=[_interview_out(r, panel) for r in rows])


@router.delete("/proposal", status_code=status.HTTP_204_NO_CONTENT)
def discard(drive_id: uuid.UUID, db: Session = Depends(get_db),
            user: User = Depends(require_coordinator)) -> None:
    scheduling.discard_proposal(db, drive_id, user.id)


@router.post("/publish", response_model=PublishOut)
def publish(drive_id: uuid.UUID, body: PublishRequest, db: Session = Depends(get_db),
            user: User = Depends(require_coordinator)) -> PublishOut:
    """Publish the pending proposal. 409 if the schedule has changed since `expected_version`."""
    version, count, dropped = scheduling.publish_schedule(db, drive_id, user.id, body.expected_version)
    return PublishOut(drive_id=drive_id, schedule_version=version, published_interviews=count,
                      superseded_dropped=dropped)


@router.post("/explain", response_model=ExplainOut)
def explain_unscheduled(drive_id: uuid.UUID, body: ExplainRequest | None = None,
                        db: Session = Depends(get_db)) -> ExplainOut:
    """Solve a fresh run and say why each left-out candidate was left out, with verified fixes.

    Read-only: nothing is saved and the pending proposal is not touched. Every suggested fix was
    checked by re-running the solver on a relaxed copy of the problem.
    """
    body = body or ExplainRequest()
    version, result, report = rescue_service.explain_schedule(db, drive_id, body.options, body.max_whatifs)

    def placed(p) -> PlacedInterviewOut:
        return PlacedInterviewOut(
            candidate_id=p.candidate_id, stage_id=p.stage_id, room_id=p.room_id,
            interviewer_ids=list(p.interviewer_ids), start_time=p.start, end_time=p.end)

    return ExplainOut(
        drive_id=drive_id,
        schedule_version=version,
        solver_status=result.status.value,
        complete=result.complete,
        scheduled=len(result.interviews),
        unscheduled_count=len(result.unscheduled),
        explanations=[
            ExplanationOut(
                candidate_id=e.candidate_id, stage_id=e.stage_id,
                reason_codes=[c.value for c in e.reason_codes], summary=e.summary,
                best_slot=e.best_slot,
                blockers=[BlockerOut(kind=b.kind.value, resource_id=b.resource_id,
                                     interviews=[placed(p) for p in b.interviews])
                          for b in e.blockers],
                fixes=[FixOut(kind=f.kind.value, description=f.description, target_id=f.target_id,
                              extra_interviews=f.extra_interviews) for f in e.fixes],
            )
            for e in report.explanations.values()
        ],
        what_ifs=[
            WhatIfOut(kind=w.kind.value, description=w.description, target_id=w.target_id,
                      total_scheduled=w.total_scheduled,
                      rescued=[RescuedKeyOut(candidate_id=c, stage_id=s) for c, s in w.rescued])
            for w in report.what_ifs
        ],
        budget_exhausted=report.budget_exhausted,
    )
