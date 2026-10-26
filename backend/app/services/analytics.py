from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    Candidate,
    DriveCandidate,
    DriveCandidateStatus,
    DriveStatus,
    Evaluation,
    Interview,
    InterviewStage,
    InterviewStatus,
    Interviewer,
    PanelAssignment,
    RecruitmentDrive,
    Room,
    User,
    UserRole,
)
from app.schemas.analytics import (
    AnalyticsOverviewOut,
    DriveAnalyticsOut,
    InterviewerAnalyticsItem,
    InterviewersAnalyticsOut,
    RecentActivityOut,
    StageAnalyticsItem,
    StageFunnelItem,
    StagesAnalyticsOut,
    UpcomingInterviewOut,
)
from app.services.errors import NotFound
from app.services.redis_service import cache_delete, cache_delete_pattern, cache_get, cache_set


def invalidate_analytics_cache(drive_id: uuid.UUID | None = None) -> None:
    """Invalidate cached analytics whenever relevant state changes."""
    cache_delete("analytics:overview")
    cache_delete("analytics:interviewers")
    if drive_id is not None:
        cache_delete(f"analytics:overview:{drive_id}")
        cache_delete(f"analytics:drive:{drive_id}")
        cache_delete(f"analytics:stages:{drive_id}")
    else:
        cache_delete_pattern("analytics:*")


def get_overview_analytics(
    db: Session,
    force_refresh: bool = False,
    drive_id: uuid.UUID | None = None,
) -> AnalyticsOverviewOut:
    """Compute global recruitment platform analytics across all drives."""
    cache_key = f"analytics:overview:{drive_id}" if drive_id else "analytics:overview"
    if not force_refresh:
        cached = cache_get(cache_key)
        if cached:
            return AnalyticsOverviewOut.model_validate(cached)

    now_str = datetime.now(timezone.utc).isoformat()

    # 1. Drives
    drives = list(db.scalars(select(RecruitmentDrive)))
    total_drives = len(drives)
    active_drives = sum(1 for d in drives if d.status in (DriveStatus.COLLECTING_AVAILABILITY, DriveStatus.PUBLISHED, DriveStatus.IN_PROGRESS))
    completed_drives = sum(1 for d in drives if d.status == DriveStatus.COMPLETED)

    # 2. Candidates
    total_candidates_registered = db.scalar(select(func.count(Candidate.user_id))) or 0
    total_candidates_enrolled = db.scalar(select(func.count(DriveCandidate.candidate_id))) or 0

    # 3. Interviews
    reportable_interview_statuses = (
        InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED, InterviewStatus.COMPLETED,
    )
    total_interviews = db.scalar(
        select(func.count(Interview.id)).where(Interview.status.in_(reportable_interview_statuses))
    ) or 0
    completed_interviews = db.scalar(
        select(func.count(Interview.id)).where(Interview.status == InterviewStatus.COMPLETED)
    ) or 0
    global_completion_rate = (
        round((completed_interviews / total_interviews * 100.0), 2)
        if total_interviews > 0
        else 0.0
    )

    # 4. Evaluations & Calibration
    evals = list(db.scalars(select(Evaluation)))
    total_evals = len(evals)
    scores = [float(e.score) for e in evals]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None

    # Count each active panel assignment that has not yet submitted feedback.
    now = datetime.now(timezone.utc)
    submitted_by_panelist = select(Evaluation.id).where(
        Evaluation.interview_id == PanelAssignment.interview_id,
        Evaluation.interviewer_id == PanelAssignment.interviewer_id,
    ).exists()
    pending_evaluations = db.scalar(
        select(func.count()).select_from(PanelAssignment)
        .join(Interview, Interview.id == PanelAssignment.interview_id)
        .where(
            PanelAssignment.is_active.is_(True),
            Interview.start_time <= now,
            Interview.status.in_((InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED, InterviewStatus.COMPLETED)),
            ~submitted_by_panelist,
        )
    ) or 0

    upcoming_query = select(Interview).join(InterviewStage, InterviewStage.id == Interview.stage_id).where(
            Interview.status.in_((InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED)),
            Interview.start_time >= now,
        )
    if drive_id is not None:
        upcoming_query = upcoming_query.where(InterviewStage.drive_id == drive_id)
    upcoming_rows = list(db.scalars(upcoming_query.order_by(Interview.start_time.asc()).limit(6)))
    upcoming = []
    for interview in upcoming_rows:
        stage = interview.stage
        drive = stage.drive if stage else None
        candidate = interview.candidate.user if interview.candidate else None
        if stage and drive and candidate:
            upcoming.append(UpcomingInterviewOut(
                interview_id=interview.id,
                drive_id=drive.id,
                drive_title=drive.title,
                stage_name=stage.name,
                candidate_name=candidate.name,
                room_name=interview.room.name if interview.room else None,
                start_time=interview.start_time,
                end_time=interview.end_time,
            ))

    activity_rows = list(db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action.in_([
            "schedule.publish", "schedule.rescue", "booking.confirm",
            "evaluation.submit", "pipeline.advance", "pipeline.reject",
        ]))
        .order_by(AuditEvent.timestamp.desc())
        .limit(6)
    ))
    recent_activity = [
        RecentActivityOut(action=e.action, entity_type=e.entity_type, timestamp=e.timestamp)
        for e in activity_rows
    ]

    result = AnalyticsOverviewOut(
        total_drives=total_drives,
        active_drives=active_drives,
        completed_drives=completed_drives,
        total_candidates_registered=total_candidates_registered,
        total_candidates_enrolled=total_candidates_enrolled,
        total_interviews_scheduled=total_interviews,
        total_interviews_completed=completed_interviews,
        global_completion_rate=global_completion_rate,
        total_evaluations_submitted=total_evals,
        average_score_across_all_evaluations=avg_score,
        pending_evaluations_count=int(pending_evaluations),
        upcoming_interviews=upcoming,
        recent_activity=recent_activity,
        generated_at=now_str,
    )
    cache_set(cache_key, result.model_dump(mode="json"), ttl_seconds=120)
    return result


def get_drive_analytics(db: Session, drive_id: uuid.UUID, force_refresh: bool = False) -> DriveAnalyticsOut:
    """Compute comprehensive drive-specific conversion, pipeline funnel, and resource utilization metrics."""
    cache_key = f"analytics:drive:{drive_id}"
    if not force_refresh:
        cached = cache_get(cache_key)
        if cached:
            return DriveAnalyticsOut.model_validate(cached)

    drive = db.get(RecruitmentDrive, drive_id)
    if not drive:
        raise NotFound("Recruitment drive not found")

    now_str = datetime.now(timezone.utc).isoformat()

    # Candidates breakdown
    candidates = list(db.scalars(select(DriveCandidate).where(DriveCandidate.drive_id == drive.id)))
    total_enrolled = len(candidates)
    active = sum(1 for c in candidates if c.status == DriveCandidateStatus.ACTIVE)
    selected = sum(1 for c in candidates if c.status == DriveCandidateStatus.SELECTED)
    rejected = sum(1 for c in candidates if c.status == DriveCandidateStatus.REJECTED)
    withdrawn = sum(1 for c in candidates if c.status == DriveCandidateStatus.WITHDRAWN)
    selection_rate = round((selected / total_enrolled * 100.0), 2) if total_enrolled > 0 else 0.0

    # Interviews
    interviews = list(
        db.scalars(
            select(Interview)
            .join(InterviewStage, InterviewStage.id == Interview.stage_id)
            .where(InterviewStage.drive_id == drive.id)
        )
    )
    total_interviews = len(interviews)
    completed_interviews = sum(1 for i in interviews if i.status == InterviewStatus.COMPLETED)
    cancelled_interviews = sum(1 for i in interviews if i.status in (InterviewStatus.CANCELLED, InterviewStatus.NO_SHOW))
    completion_rate = round((completed_interviews / total_interviews * 100.0), 2) if total_interviews > 0 else 0.0

    # Pending feedback
    completed_rows = [i for i in interviews if i.status == InterviewStatus.COMPLETED]
    pending_feedback = 0
    for iv in completed_rows:
        evaluated_ivrs = {e.interviewer_id for e in iv.evaluations}
        active_panelists = {p.interviewer_id for p in iv.panel if p.is_active}
        pending_feedback += len(active_panelists - evaluated_ivrs)

    # Stages & Conversion Funnel
    stages = sorted(drive.stages, key=lambda s: s.order_index)
    total_stages = len(stages)
    funnel: list[StageFunnelItem] = []

    for idx, st in enumerate(stages):
        stage_cands = [c for c in candidates if c.current_stage_id == st.id or c.status == DriveCandidateStatus.SELECTED]
        passed_count = sum(
            1 for c in candidates
            if (c.status == DriveCandidateStatus.SELECTED) or
               (c.current_stage and c.current_stage.order_index > st.order_index)
        )
        failed_count = sum(
            1 for c in candidates
            if c.status == DriveCandidateStatus.REJECTED and c.current_stage_id == st.id
        )
        in_stage = len(stage_cands)
        pending = sum(
            1 for c in candidates
            if c.status == DriveCandidateStatus.ACTIVE and c.current_stage_id == st.id
        )

        conversion_rate = (
            round((passed_count / (passed_count + failed_count) * 100.0), 2)
            if (passed_count + failed_count) > 0
            else 100.0 if passed_count > 0 else 0.0
        )

        funnel.append(
            StageFunnelItem(
                stage_id=st.id,
                stage_name=st.name,
                order_index=st.order_index,
                stage_type=st.stage_type.value,
                candidates_count=in_stage,
                passed_count=passed_count,
                failed_count=failed_count,
                pending_count=pending,
                conversion_rate=conversion_rate,
            )
        )

    # Room utilization
    rooms = list(db.scalars(select(Room).where(Room.is_active.is_(True))))
    horizon_hours = max((drive.window_end - drive.window_start).total_seconds() / 3600.0, 1.0)
    total_room_hours = len(rooms) * horizon_hours
    booked_hours = sum((iv.end_time - iv.start_time).total_seconds() / 3600.0 for iv in interviews if iv.status != InterviewStatus.CANCELLED)
    room_utilization = round(min(booked_hours / total_room_hours * 100.0, 100.0), 2) if total_room_hours > 0 else 0.0

    # Rescue operations count
    rescue_count = db.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.entity_id == drive.id,
            AuditEvent.action == "schedule.rescue",
        )
    ) or 0

    result = DriveAnalyticsOut(
        drive_id=drive.id,
        drive_title=drive.title,
        drive_status=drive.status.value,
        timezone=drive.timezone,
        window_start=drive.window_start.isoformat(),
        window_end=drive.window_end.isoformat(),
        total_enrolled=total_enrolled,
        active_in_pipeline=active,
        selected_count=selected,
        rejected_count=rejected,
        withdrawn_count=withdrawn,
        overall_selection_rate=selection_rate,
        interview_completion_rate=completion_rate,
        total_interviews=total_interviews,
        completed_interviews=completed_interviews,
        cancelled_interviews=cancelled_interviews,
        pending_feedback_count=pending_feedback,
        stage_funnel=funnel,
        average_stage_duration_hours=round(sum(st.duration_minutes for st in stages) / (len(stages) * 60.0), 2) if stages else 0.0,
        room_utilization_percent=room_utilization,
        rescue_operations_count=rescue_count,
        generated_at=now_str,
    )
    cache_set(cache_key, result.model_dump(mode="json"), ttl_seconds=120)
    return result


def get_stages_analytics(db: Session, drive_id: uuid.UUID, force_refresh: bool = False) -> StagesAnalyticsOut:
    """Compute score distributions and conversion metrics for all stages of a drive."""
    cache_key = f"analytics:stages:{drive_id}"
    if not force_refresh:
        cached = cache_get(cache_key)
        if cached:
            return StagesAnalyticsOut.model_validate(cached)

    drive = db.get(RecruitmentDrive, drive_id)
    if not drive:
        raise NotFound("Recruitment drive not found")

    now_str = datetime.now(timezone.utc).isoformat()
    stages = sorted(drive.stages, key=lambda s: s.order_index)
    stage_items: list[StageAnalyticsItem] = []

    for st in stages:
        # Collect evaluations in this stage
        evals = list(
            db.scalars(
                select(Evaluation)
                .join(Interview, Interview.id == Evaluation.interview_id)
                .where(Interview.stage_id == st.id)
            )
        )
        scores = [float(e.score) for e in evals]
        avg_score = round(statistics.mean(scores), 2) if scores else None
        min_score = min(scores) if scores else None
        max_score = max(scores) if scores else None
        median_score = round(statistics.median(scores), 2) if scores else None

        # Interviews count
        interviews = list(db.scalars(select(Interview).where(Interview.stage_id == st.id)))
        scheduled_count = len(interviews)
        completed_count = sum(1 for i in interviews if i.status == InterviewStatus.COMPLETED)

        # Candidates count entered
        candidates = list(db.scalars(select(DriveCandidate).where(DriveCandidate.drive_id == drive.id)))
        entered = sum(1 for c in candidates if c.current_stage and c.current_stage.order_index >= st.order_index or c.status == DriveCandidateStatus.SELECTED)
        passed = sum(1 for c in candidates if (c.status == DriveCandidateStatus.SELECTED) or (c.current_stage and c.current_stage.order_index > st.order_index))

        conv_rate = round(passed / entered * 100.0, 2) if entered > 0 else 0.0
        dropoff = round(100.0 - conv_rate, 2)

        stage_items.append(
            StageAnalyticsItem(
                stage_id=st.id,
                stage_name=st.name,
                order_index=st.order_index,
                stage_type=st.stage_type.value,
                duration_minutes=st.duration_minutes,
                panel_size=st.panel_size,
                total_candidates_entered=entered,
                conversion_rate=conv_rate,
                dropoff_rate=dropoff,
                average_score=avg_score,
                min_score=min_score,
                max_score=max_score,
                median_score=median_score,
                interviews_completed=completed_count,
                interviews_scheduled=scheduled_count,
            )
        )

    result = StagesAnalyticsOut(
        drive_id=drive.id,
        drive_title=drive.title,
        stages=stage_items,
        generated_at=now_str,
    )
    cache_set(cache_key, result.model_dump(mode="json"), ttl_seconds=120)
    return result


def get_interviewers_analytics(db: Session, force_refresh: bool = False) -> InterviewersAnalyticsOut:
    """Compute workload distribution, capacity utilization, and evaluator calibration."""
    cache_key = "analytics:interviewers"
    if not force_refresh:
        cached = cache_get(cache_key)
        if cached:
            return InterviewersAnalyticsOut.model_validate(cached)

    now_str = datetime.now(timezone.utc).isoformat()
    interviewers = list(db.scalars(select(Interviewer)))

    # Global score average for calibration calculation
    all_evals = list(db.scalars(select(Evaluation)))
    global_avg = statistics.mean([float(e.score) for e in all_evals]) if all_evals else 7.0

    items: list[InterviewerAnalyticsItem] = []
    for ivr in interviewers:
        u = ivr.user
        if not u:
            continue

        # Assigned interviews
        assigned_panels = list(
            db.scalars(
                select(PanelAssignment)
                .where(
                    PanelAssignment.interviewer_id == ivr.user_id,
                    PanelAssignment.is_active.is_(True),
                )
            )
        )
        total_assigned = len(assigned_panels)

        # Completed interviews
        completed_count = db.scalar(
            select(func.count(PanelAssignment.interview_id))
            .join(Interview, Interview.id == PanelAssignment.interview_id)
            .where(
                PanelAssignment.interviewer_id == ivr.user_id,
                PanelAssignment.is_active.is_(True),
                Interview.status == InterviewStatus.COMPLETED,
            )
        ) or 0

        # Evaluations submitted by this interviewer
        my_evals = list(db.scalars(select(Evaluation).where(Evaluation.interviewer_id == ivr.user_id)))
        scores = [float(e.score) for e in my_evals]
        avg_score = round(statistics.mean(scores), 2) if scores else None

        # Evaluator calibration: harsh, generous, calibrated
        calibration = "calibrated"
        if avg_score is not None and len(scores) >= 3:
            if avg_score > global_avg + 1.2:
                calibration = "generous"
            elif avg_score < global_avg - 1.2:
                calibration = "harsh"

        pending_evals = max(completed_count - len(my_evals), 0)
        # Utilization rate (% of max daily capacity over 5 days)
        weekly_capacity = max(ivr.capacity * 5, 1)
        utilization_rate = round(min(total_assigned / weekly_capacity * 100.0, 100.0), 2)

        items.append(
            InterviewerAnalyticsItem(
                interviewer_id=ivr.user_id,
                name=u.name,
                email=u.email,
                department=ivr.department or "Core Engineering",
                capacity_per_day=ivr.capacity,
                skills=list(ivr.skills or []),
                total_assigned_interviews=total_assigned,
                completed_interviews=completed_count,
                pending_evaluations=pending_evals,
                utilization_rate=utilization_rate,
                average_score_given=avg_score,
                evaluator_calibration=calibration,
            )
        )

    items.sort(key=lambda x: x.total_assigned_interviews, reverse=True)
    result = InterviewersAnalyticsOut(
        total_interviewers=len(items),
        interviewers=items,
        generated_at=now_str,
    )
    cache_set(cache_key, result.model_dump(mode="json"), ttl_seconds=120)
    return result
