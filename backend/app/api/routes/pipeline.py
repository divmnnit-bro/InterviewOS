from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_coordinator
from app.db.database import get_db
from app.models import DriveCandidateStatus, User
from app.schemas.pipeline import CandidateStageDecision, DecisionOut, PipelineStatusResponse
from app.services import pipeline as svc

router = APIRouter(tags=["pipeline"], dependencies=[Depends(require_coordinator)])


@router.post("/drives/{drive_id}/candidates/{candidate_id}/advance", response_model=DecisionOut)
def advance(drive_id: uuid.UUID, candidate_id: uuid.UUID, body: CandidateStageDecision,
            db: Session = Depends(get_db), user: User = Depends(require_coordinator)) -> DecisionOut:
    """Pass the candidate: next round, or SELECTED after the last. 409 if the feedback does not support it."""
    return svc.advance_candidate(db, drive_id, candidate_id, body, user)


@router.post("/drives/{drive_id}/candidates/{candidate_id}/reject", response_model=DecisionOut)
def reject(drive_id: uuid.UUID, candidate_id: uuid.UUID, body: CandidateStageDecision,
           db: Session = Depends(get_db), user: User = Depends(require_coordinator)) -> DecisionOut:
    """Reject the candidate and cancel their interviews that have not started."""
    return svc.reject_candidate(db, drive_id, candidate_id, body, user)


@router.get("/drives/{drive_id}/pipeline", response_model=PipelineStatusResponse)
def pipeline(drive_id: uuid.UUID, status: DriveCandidateStatus | None = Query(default=None),
             db: Session = Depends(get_db)) -> PipelineStatusResponse:
    """Every candidate's progress through every round. `status` filters the candidate list only."""
    return svc.pipeline_status(db, drive_id, status)
