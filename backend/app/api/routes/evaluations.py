from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.db.database import get_db
from app.models import Evaluation, User
from app.schemas.evaluation import EvaluationCreate, EvaluationRead, InterviewEvaluationsOut
from app.services import evaluations as svc

router = APIRouter(tags=["evaluations"])


@router.post("/interviews/{interview_id}/evaluations", response_model=EvaluationRead)
def submit(interview_id: uuid.UUID, body: EvaluationCreate, response: Response,
           db: Session = Depends(get_db), user: User = Depends(require_staff)) -> Evaluation:
    """Submit feedback for an interview you are on the panel of (coordinators: set `on_behalf_of`).

    201 the first time, 200 when it revises the author's earlier feedback.
    """
    evaluation, created = svc.submit_evaluation(db, interview_id, user, body)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return evaluation


@router.get("/interviews/{interview_id}/evaluations", response_model=InterviewEvaluationsOut)
def read(interview_id: uuid.UUID, db: Session = Depends(get_db),
         user: User = Depends(require_staff)) -> InterviewEvaluationsOut:
    """Coordinators see all feedback; a panelist sees colleagues' only after submitting their own."""
    return svc.get_interview_evaluations(db, interview_id, user)
