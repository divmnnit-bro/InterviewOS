"""Interview feedback: who may write it, who may read it, and when it stops changing.

Writing   Only a member of the interview's panel, or a coordinator on a panel member's behalf.
          The interview must have started and not be cancelled. A panelist may revise their own
          feedback until the candidate's result for the round is recorded.
Reading   Coordinators see everything. A panelist sees colleagues' feedback only after submitting
          their own, so feedback is written independently. Anyone else gets "not found".
When every active panel member has submitted and the interview has ended, it is marked COMPLETED.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    Evaluation,
    Interview,
    InterviewStatus,
    PanelAssignment,
    User,
    UserRole,
)
from app.schemas.evaluation import EvaluationCreate, EvaluationRead, InterviewEvaluationsOut
from app.services.errors import Conflict, EvaluationLocked, Forbidden, NotFound, Unprocessable
from app.services.interviews import get_interview
from app.services.pipeline import decision_recorded

# Statuses in which an interview can have been held.
_EVALUABLE = (InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED, InterviewStatus.COMPLETED)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _active_panel(db: Session, interview_id: uuid.UUID) -> set[uuid.UUID]:
    return set(db.scalars(
        select(PanelAssignment.interviewer_id).where(
            PanelAssignment.interview_id == interview_id, PanelAssignment.is_active.is_(True))
    ))


def _lock_interview(db: Session, interview_id: uuid.UUID) -> Interview:
    """Lock the interview row so concurrent submissions for it run one at a time."""
    iv = db.execute(
        select(Interview).where(Interview.id == interview_id)
        .with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if iv is None:
        raise NotFound("interview not found")
    return iv


def _resolve_author(actor: User, payload: EvaluationCreate, panel: set[uuid.UUID]) -> uuid.UUID:
    if actor.role == UserRole.INTERVIEWER:
        if payload.on_behalf_of not in (None, actor.id):
            raise Forbidden("you can only submit your own feedback")
        if actor.id not in panel:
            raise NotFound("interview not found")      # same answer as a missing interview
        return actor.id
    if actor.role == UserRole.COORDINATOR:
        if payload.on_behalf_of is None:
            raise Unprocessable("name the panel member this feedback is for in `on_behalf_of`")
        if payload.on_behalf_of not in panel:
            raise Unprocessable("that interviewer is not on this interview's panel")
        return payload.on_behalf_of
    raise Forbidden("you do not have permission to do this")


def submit_evaluation(
    db: Session, interview_id: uuid.UUID, actor: User, payload: EvaluationCreate
) -> tuple[Evaluation, bool]:
    """Create or update the author's feedback. Returns (evaluation, created)."""
    try:
        iv = _lock_interview(db, interview_id)
        panel = _active_panel(db, interview_id)
        author = _resolve_author(actor, payload, panel)

        now = _now()
        if iv.status not in _EVALUABLE:
            raise Conflict(f"an interview that is {iv.status.value} cannot be evaluated")
        if iv.start_time > now:
            raise Conflict("this interview has not started yet")
        if decision_recorded(db, iv):
            raise EvaluationLocked("the candidate's result for this round is recorded; feedback is locked")

        score = payload.overall_score()
        existing = db.scalars(
            select(Evaluation).where(
                Evaluation.interview_id == iv.id, Evaluation.interviewer_id == author)
        ).first()
        created = existing is None
        if existing is None:
            evaluation = Evaluation(
                interview_id=iv.id, interviewer_id=author, score=score, rubric=payload.rubric,
                feedback=payload.feedback, recommendation=payload.recommendation)
            db.add(evaluation)
        else:
            evaluation = existing
            evaluation.score = score
            evaluation.rubric = payload.rubric
            evaluation.feedback = payload.feedback
            evaluation.recommendation = payload.recommendation
        db.flush()

        evaluated = set(db.scalars(
            select(Evaluation.interviewer_id).where(Evaluation.interview_id == iv.id)))
        completed_now = False
        if panel and not (panel - evaluated) and iv.status != InterviewStatus.COMPLETED \
                and now >= iv.end_time:
            iv.status = InterviewStatus.COMPLETED
            completed_now = True

        db.add(AuditEvent(
            actor_id=actor.id,
            action="evaluation.submit" if created else "evaluation.update",
            entity_type="interview", entity_id=iv.id,
            # The feedback text itself is deliberately not copied into the audit log.
            details={
                "evaluation_id": str(evaluation.id), "author_id": str(author),
                "on_behalf_of": author != actor.id, "score": score,
                "recommendation": payload.recommendation.value, "interview_completed": completed_now,
            },
        ))
        db.commit()
        return evaluation, created
    except Exception:
        db.rollback()
        raise


def get_interview_evaluations(
    db: Session, interview_id: uuid.UUID, user: User
) -> InterviewEvaluationsOut:
    """Feedback the user is allowed to see on this interview."""
    iv = get_interview(db, interview_id)
    panel = _active_panel(db, iv.id)
    evaluations = list(db.scalars(
        select(Evaluation).where(Evaluation.interview_id == iv.id)
        .order_by(Evaluation.submitted_at, Evaluation.id)
    ))

    if user.role == UserRole.COORDINATOR:
        visible, visibility = evaluations, "all"
    elif user.role == UserRole.INTERVIEWER:
        mine = [e for e in evaluations if e.interviewer_id == user.id]
        if user.id not in panel and not mine:
            raise NotFound("interview not found")
        # Colleagues' feedback is revealed only once the reader has written their own.
        visible, visibility = (evaluations, "all") if mine else ([], "own_only")
    else:
        raise Forbidden("you do not have permission to do this")

    return InterviewEvaluationsOut(
        interview_id=iv.id, visibility=visibility, panel_size=len(panel),
        submitted_count=len(evaluations),
        evaluations=[EvaluationRead.model_validate(e) for e in visible])
