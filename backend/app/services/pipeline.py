"""Moving candidates through a drive: advance, reject, and the pipeline overview.

A candidate's place in the pipeline is their `DriveCandidate` row: `status` plus `current_stage_id`
(the round they are in now). Passing the last round marks them SELECTED. Every decision locks that
row, checks it is for the round the candidate is actually in, and writes an audit event.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    DriveCandidate,
    DriveCandidateStatus,
    DriveStatus,
    Evaluation,
    Interview,
    InterviewStage,
    InterviewStatus,
    PanelAssignment,
    RecruitmentDrive,
    User,
)
from app.schemas.pipeline import (
    CandidateStageDecision,
    DecisionOut,
    PipelineCandidate,
    PipelineStageSummary,
    PipelineStatusResponse,
    StageProgress,
)
from app.services.errors import Conflict, DecisionBlocked, NotFound
from app.services.pipeline_rules import (
    StageState,
    average,
    decision_blockers,
    rule_met,
    stage_state,
)
from app.services.scheduling import get_drive

# Interviews that really happened or will: the ones a decision is based on.
_LIVE = (InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED, InterviewStatus.COMPLETED)
# Not yet held: cancelled when the candidate is rejected.
_CANCELLABLE = (InterviewStatus.PROPOSED, InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED)
_CLOSED_DRIVES = (DriveStatus.COMPLETED, DriveStatus.ARCHIVED)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def current_stage_id(enrollment: DriveCandidate, stages: list[InterviewStage]) -> uuid.UUID | None:
    """The round a candidate is in: their stored stage, else the drive's first."""
    ids = [s.id for s in stages]
    if enrollment.current_stage_id in ids:
        return enrollment.current_stage_id
    return ids[0] if ids else None


def decision_recorded(db: Session, interview: Interview) -> bool:
    """True once the candidate has been passed on, rejected, selected or withdrawn for this interview's round."""
    stage = interview.stage
    enrollment = db.get(DriveCandidate, (stage.drive_id, interview.candidate_id))
    if enrollment is None:
        return False
    stages = list(stage.drive.stages)
    return (enrollment.status != DriveCandidateStatus.ACTIVE
            or current_stage_id(enrollment, stages) != interview.stage_id)


# ------------------------------------------------------------------ evidence


@dataclass
class Evidence:
    interview: Interview | None = None
    scores: list[float] = field(default_factory=list)
    panel: set[uuid.UUID] = field(default_factory=set)       # active panel members
    evaluated: set[uuid.UUID] = field(default_factory=set)   # who has given feedback

    @property
    def average(self) -> float | None:
        return average(self.scores)


def gather_evidence(db: Session, candidate_id: uuid.UUID, stage_id: uuid.UUID) -> Evidence:
    """The candidate's latest real interview in this round, with its feedback."""
    iv = db.scalars(
        select(Interview)
        .where(Interview.candidate_id == candidate_id, Interview.stage_id == stage_id,
               Interview.status.in_(_LIVE))
        .order_by(Interview.start_time.desc())
        .limit(1)
    ).first()
    if iv is None:
        return Evidence()
    evals = list(db.scalars(select(Evaluation).where(Evaluation.interview_id == iv.id)))
    panel = set(db.scalars(
        select(PanelAssignment.interviewer_id).where(
            PanelAssignment.interview_id == iv.id, PanelAssignment.is_active.is_(True))
    ))
    return Evidence(iv, [float(e.score) for e in evals], panel, {e.interviewer_id for e in evals})


# ------------------------------------------------------------------ decisions


def _lock_enrollment(db: Session, drive_id: uuid.UUID, candidate_id: uuid.UUID) -> DriveCandidate:
    row = db.execute(
        select(DriveCandidate)
        .where(DriveCandidate.drive_id == drive_id, DriveCandidate.candidate_id == candidate_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("candidate is not enrolled in this drive")
    return row


def _open_decision(
    db: Session, drive_id: uuid.UUID, candidate_id: uuid.UUID, decision: CandidateStageDecision
) -> tuple[RecruitmentDrive, list[InterviewStage], DriveCandidate, InterviewStage]:
    """Load and validate everything a decision needs. Locks the candidate's enrolment row."""
    drive = get_drive(db, drive_id)
    if drive.status in _CLOSED_DRIVES:
        raise Conflict(f"drive is {drive.status.value}; decisions can no longer be recorded")
    enrollment = _lock_enrollment(db, drive_id, candidate_id)
    if enrollment.status != DriveCandidateStatus.ACTIVE:
        raise Conflict(f"candidate is already {enrollment.status.value}")
    stages = list(drive.stages)
    current = current_stage_id(enrollment, stages)
    if current is None:
        raise Conflict("the drive has no stages")
    if decision.stage_id != current:
        raise Conflict("the candidate is not in that round (it may already have been decided); reload and retry",
                       details={"current_stage_id": str(current)})
    stage = next(s for s in stages if s.id == current)
    return drive, stages, enrollment, stage


def advance_candidate(
    db: Session, drive_id: uuid.UUID, candidate_id: uuid.UUID,
    decision: CandidateStageDecision, actor: User,
) -> DecisionOut:
    """Pass the candidate: move to the next round, or become SELECTED after the last one."""
    try:
        _, stages, enrollment, stage = _open_decision(db, drive_id, candidate_id, decision)
        evidence = gather_evidence(db, candidate_id, stage.id)
        avg = evidence.average
        blockers = decision_blockers(
            has_interview=evidence.interview is not None, panel=evidence.panel,
            evaluated=evidence.evaluated, avg=avg, rule=stage.rule)
        if blockers and not decision.override:
            raise DecisionBlocked(
                "this pass is not supported by the round's feedback; fix that or override with a reason",
                details=blockers)

        later = [s for s in stages if s.order_index > stage.order_index]
        if later:
            enrollment.current_stage_id = later[0].id
            outcome = "advanced"
        else:
            enrollment.status = DriveCandidateStatus.SELECTED
            outcome = "selected"

        db.add(AuditEvent(
            actor_id=actor.id, action="pipeline.advance", entity_type="drive_candidate",
            entity_id=candidate_id,
            details={
                "drive_id": str(drive_id), "from_stage_id": str(stage.id),
                "to_stage_id": str(enrollment.current_stage_id) if outcome == "advanced" else None,
                "outcome": outcome, "average_score": avg, "rule_met": rule_met(stage.rule, avg),
                "override_used": bool(blockers) and decision.override,
                "overridden": [b["code"] for b in blockers] if decision.override else [],
                "override_reason": decision.override_reason if decision.override else None,
                "notes": decision.notes,
            },
        ))
        db.commit()
        from app.services.analytics import invalidate_analytics_cache
        invalidate_analytics_cache(drive_id)
        return DecisionOut(
            drive_id=drive_id, candidate_id=candidate_id, outcome=outcome, status=enrollment.status,
            from_stage_id=stage.id, current_stage_id=enrollment.current_stage_id,
            average_score=avg, rule_met=rule_met(stage.rule, avg),
            override_used=bool(blockers) and decision.override)
    except Exception:
        db.rollback()
        raise


def reject_candidate(
    db: Session, drive_id: uuid.UUID, candidate_id: uuid.UUID,
    decision: CandidateStageDecision, actor: User,
) -> DecisionOut:
    """Reject the candidate. Their interviews that have not happened yet are cancelled."""
    try:
        drive, stages, enrollment, stage = _open_decision(db, drive_id, candidate_id, decision)
        evidence = gather_evidence(db, candidate_id, stage.id)
        avg = evidence.average
        enrollment.status = DriveCandidateStatus.REJECTED

        cancelled = _cancel_future_interviews(db, candidate_id, [s.id for s in stages])
        db.add(AuditEvent(
            actor_id=actor.id, action="pipeline.reject", entity_type="drive_candidate",
            entity_id=candidate_id,
            details={
                "drive_id": str(drive_id), "stage_id": str(stage.id), "average_score": avg,
                "rule_met": rule_met(stage.rule, avg), "notes": decision.notes,
                "cancelled_interview_ids": [str(i) for i in cancelled],
            },
        ))
        db.commit()
        from app.services.analytics import invalidate_analytics_cache
        invalidate_analytics_cache(drive_id)
        return DecisionOut(
            drive_id=drive_id, candidate_id=candidate_id, outcome="rejected", status=enrollment.status,
            from_stage_id=stage.id, current_stage_id=enrollment.current_stage_id,
            average_score=avg, rule_met=rule_met(stage.rule, avg), override_used=False,
            cancelled_interviews=len(cancelled))
    except Exception:
        db.rollback()
        raise


def _cancel_future_interviews(
    db: Session, candidate_id: uuid.UUID, stage_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    """Cancel interviews that have not started, freeing their rooms and panel members."""
    ids = list(db.scalars(
        select(Interview.id).where(
            Interview.candidate_id == candidate_id, Interview.stage_id.in_(stage_ids),
            Interview.status.in_(_CANCELLABLE), Interview.start_time > _now())
    ))
    if ids:
        # Panel rows first: an inactive row no longer occupies the interviewer's slot.
        db.execute(update(PanelAssignment).where(PanelAssignment.interview_id.in_(ids))
                   .values(is_active=False))
        db.execute(update(Interview).where(Interview.id.in_(ids))
                   .values(status=InterviewStatus.CANCELLED, version=Interview.version + 1))
    return ids


# ------------------------------------------------------------------ overview


def pipeline_status(
    db: Session, drive_id: uuid.UUID, status_filter: DriveCandidateStatus | None = None
) -> PipelineStatusResponse:
    """Every candidate's progress through every round. `status_filter` narrows the candidate list only."""
    drive = get_drive(db, drive_id)
    stages = list(drive.stages)
    index = {s.id: n for n, s in enumerate(stages)}
    stage_ids = list(index)

    rows = db.execute(
        select(DriveCandidate, User.name, User.email)
        .join(User, User.id == DriveCandidate.candidate_id)
        .where(DriveCandidate.drive_id == drive_id)
        .order_by(User.name, DriveCandidate.candidate_id)
    ).all()

    # Latest real interview per (candidate, round).
    latest: dict[tuple[uuid.UUID, uuid.UUID], Interview] = {}
    if stage_ids:
        for iv in db.scalars(
            select(Interview).where(Interview.stage_id.in_(stage_ids), Interview.status.in_(_LIVE))
            .order_by(Interview.start_time)
        ):
            latest[(iv.candidate_id, iv.stage_id)] = iv          # later start overwrites earlier
    iv_ids = [iv.id for iv in latest.values()]

    scores: dict[uuid.UUID, tuple[int, float | None]] = {}
    evaluated_active: dict[uuid.UUID, int] = {}
    panel_active: dict[uuid.UUID, int] = {}
    if iv_ids:
        for iid, n, avg in db.execute(
            select(Evaluation.interview_id, func.count(), func.avg(Evaluation.score))
            .where(Evaluation.interview_id.in_(iv_ids)).group_by(Evaluation.interview_id)
        ):
            scores[iid] = (n, round(float(avg), 2) if avg is not None else None)
        for iid, n in db.execute(
            select(PanelAssignment.interview_id, func.count())
            .where(PanelAssignment.interview_id.in_(iv_ids), PanelAssignment.is_active.is_(True))
            .group_by(PanelAssignment.interview_id)
        ):
            panel_active[iid] = n
        for iid, n in db.execute(
            select(Evaluation.interview_id, func.count())
            .join(PanelAssignment, (PanelAssignment.interview_id == Evaluation.interview_id)
                  & (PanelAssignment.interviewer_id == Evaluation.interviewer_id))
            .where(Evaluation.interview_id.in_(iv_ids), PanelAssignment.is_active.is_(True))
            .group_by(Evaluation.interview_id)
        ):
            evaluated_active[iid] = n

    counts = {s.value: 0 for s in DriveCandidateStatus}
    summary = {s.id: {"here": 0, "awaiting": 0, "passed": 0, "rejected": 0} for s in stages}
    candidates: list[PipelineCandidate] = []

    for enrollment, name, email in rows:
        counts[enrollment.status.value] += 1
        cur = current_stage_id(enrollment, stages)
        cur_idx = index.get(cur, -1)
        progress: list[StageProgress] = []
        for n, stage in enumerate(stages):
            iv = latest.get((enrollment.candidate_id, stage.id))
            n_evals, avg = scores.get(iv.id, (0, None)) if iv else (0, None)
            panel_n = panel_active.get(iv.id, 0) if iv else 0
            complete = panel_n > 0 and evaluated_active.get(iv.id, 0) >= panel_n
            state = stage_state(
                enrollment_status=enrollment.status.value, stage_index=n, current_index=cur_idx,
                has_interview=iv is not None, feedback_complete=complete)
            progress.append(StageProgress(
                stage_id=stage.id, order_index=stage.order_index, name=stage.name, state=state,
                interview_id=iv.id if iv else None, interview_status=iv.status.value if iv else None,
                evaluations=n_evals, average_score=avg, rule_met=rule_met(stage.rule, avg)))
            bucket = summary[stage.id]
            if state is StageState.PASSED:
                bucket["passed"] += 1
            elif state is StageState.REJECTED:
                bucket["rejected"] += 1
            elif state in (StageState.PENDING, StageState.INTERVIEWING, StageState.AWAITING_DECISION):
                bucket["here"] += 1
                if state is StageState.AWAITING_DECISION:
                    bucket["awaiting"] += 1
        if status_filter is None or enrollment.status == status_filter:
            candidates.append(PipelineCandidate(
                candidate_id=enrollment.candidate_id, name=name, email=email,
                status=enrollment.status, current_stage_id=cur, stages=progress))

    return PipelineStatusResponse(
        drive_id=drive.id, title=drive.title, status_counts=counts,
        stages=[PipelineStageSummary(
            stage_id=s.id, order_index=s.order_index, name=s.name,
            candidates_here=summary[s.id]["here"], awaiting_decision=summary[s.id]["awaiting"],
            passed=summary[s.id]["passed"], rejected=summary[s.id]["rejected"]) for s in stages],
        candidates=candidates)
