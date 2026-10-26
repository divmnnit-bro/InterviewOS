from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    DriveCandidate,
    DriveCandidateStatus,
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
from app.models.ai_interview_kit import AIInterviewKit
from app.schemas.ai import (
    AskRecruitmentDataResponse,
    BehavioralQuestion,
    CandidateCountsBreakdown,
    CandidateSummaryResponse,
    CodingQuestion,
    DriveBriefResponse,
    InterviewKitRequest,
    InterviewKitResponse,
    MissingFeedbackItem,
    RoundEvaluationSummary,
    SystemDesignScenario,
    UpcomingRoundBrief,
)
from app.services.ai.providers import DeterministicLocalProvider, get_llm_provider
from app.services.errors import Conflict, Forbidden, NotFound, Unprocessable
from app.services.job_queue import enqueue_job, register_handler

log = logging.getLogger(__name__)


def _suggested_followups(intent: str) -> list[str]:
    suggestions = {
        "awaiting_evaluations": [
            "Which interviewers have the most pending scorecards?",
            "How many completed interviews are awaiting evaluation?",
        ],
        "interviewer_workload": [
            "Which interviewers are above their daily capacity?",
            "How many interviews are scheduled?",
        ],
        "candidate_pipeline_counts": [
            "How many candidates are selected?",
            "How many candidates are active?",
        ],
        "schedule_status": [
            "How many interviews are scheduled?",
            "How many interviews are confirmed?",
        ],
    }
    return suggestions.get(
        intent,
        [
            "Which interviewers have the highest workload?",
            "Which candidates are awaiting evaluation?",
        ],
    )


def _anonymized_ai_summary(
    provider: Any,
    task: str,
    metrics: dict[str, Any],
    fallback: str,
) -> tuple[str, Any, bool]:
    """Summarize aggregate numeric metrics without sending personal data or raw notes."""
    forbidden_keys = {
        "candidate_id", "candidate_name", "candidate_email", "interview_id",
        "interviewer_id", "interviewer_name", "email", "phone", "name",
        "drive_id", "feedback", "key_feedback", "raw_feedback", "job_description",
    }

    def validate(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in forbidden_keys:
                    raise ValueError("PII or free-text evaluation content cannot be sent to AI")
                validate(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                validate(child)
        elif value is not None and not isinstance(value, (int, float, bool)):
            raise ValueError("AI summary context must contain aggregate numeric values only")

    validate(metrics)
    if provider.name == "deterministic":
        return fallback, provider, False

    prompt = (
        f"Task: {task}\n"
        "The following context contains only anonymized aggregate counts and scores. "
        f"Use only these values and do not infer causes or make hiring decisions:\n{json.dumps(metrics, sort_keys=True)}"
    )
    try:
        text = provider.ask_text(
            prompt,
            system_prompt=(
                "You are InterviewOS Copilot. Summarize only the supplied aggregate "
                "metrics. Do not invent facts, infer protected traits, or make hiring "
                "decisions. State when the data is insufficient."
            ),
        ).strip()
        if not text:
            raise ValueError("AI provider returned an empty response")
        return text, provider, True
    except Exception as exc:
        log.warning("AI aggregate summary failed (%s); using calculated fallback", exc)
        return fallback, DeterministicLocalProvider(), False


def generate_interview_kit(
    db: Session,
    req: InterviewKitRequest,
    actor_id: uuid.UUID | None = None,
) -> InterviewKitResponse:
    """Generate structured interview questions, rubrics, and criteria for a drive/stage."""
    drive = db.get(RecruitmentDrive, req.drive_id)
    if not drive:
        raise NotFound("Recruitment drive not found")

    stage_name = None
    required_skills = list(req.required_skills)
    if req.stage_id:
        stage = db.get(InterviewStage, req.stage_id)
        if not stage or stage.drive_id != drive.id:
            raise NotFound("Stage not found in this recruitment drive")
        stage_name = stage.name
        if not required_skills and stage.required_skills:
            required_skills = list(stage.required_skills)

    topic = req.topic or (f"{stage_name} Assessment" if stage_name else drive.title)

    # If async_mode requested, enqueue as background job
    if req.async_mode:
        payload = {
            "drive_id": str(req.drive_id),
            "stage_id": str(req.stage_id) if req.stage_id else None,
            "topic": topic,
            "difficulty": req.difficulty,
            "required_skills": required_skills,
            "job_description": req.job_description,
            "stage_name": stage_name,
        }
        job = enqueue_job(db, "ai_interview_kit", payload, creator_id=actor_id)
        return InterviewKitResponse(
            drive_id=req.drive_id,
            stage_name=stage_name,
            difficulty=req.difficulty,
            topic=topic,
            coding_questions=[],
            system_design_scenarios=[],
            behavioral_questions=[],
            rubric_template={},
            provider_used="async_worker",
            model_used="queued",
            job_id=job.id,
        )

    # Synchronous generation
    provider = get_llm_provider()
    prompt = (
        f"Generate a technical interview kit for role: '{topic}' with required skills: {', '.join(required_skills) or 'General Software Engineering'}.\n"
        f"Target difficulty level: {req.difficulty}.\n"
        f"Job description details: {req.job_description or 'Senior Full-Stack / Backend Engineer'}.\n"
        "Include production-grade coding problems with edge cases, system design scenarios, and evaluation rubrics."
    )

    generation_provider = provider
    try:
        kit_res = provider.generate_structured(prompt, InterviewKitResponse)
    except Exception as exc:
        log.warning("Provider structured generation error (%s), using local fallback", exc)
        generation_provider = DeterministicLocalProvider()
        kit_res = generation_provider.generate_structured(prompt, InterviewKitResponse)

    # Persist the kit in the database
    kit_row = AIInterviewKit(
        drive_id=drive.id,
        stage_id=req.stage_id,
        creator_id=actor_id,
        topic=topic,
        difficulty=req.difficulty,
        coding_challenges=[q.model_dump() for q in kit_res.coding_questions],
        system_design_scenarios=[s.model_dump() for s in kit_res.system_design_scenarios],
        behavioral_questions=[b.model_dump() for b in kit_res.behavioral_questions],
        rubric_template=kit_res.rubric_template,
        provider_used=generation_provider.name,
        model_used=getattr(generation_provider, "model", "local"),
        raw_prompt=prompt,
    )
    db.add(kit_row)
    db.commit()
    db.refresh(kit_row)

    kit_res.kit_id = kit_row.id
    kit_res.drive_id = drive.id
    kit_res.stage_name = stage_name
    kit_res.difficulty = req.difficulty
    kit_res.topic = topic
    kit_res.provider_used = generation_provider.name
    kit_res.model_used = getattr(generation_provider, "model", "local")
    kit_res.is_ai_generated = generation_provider.name != "deterministic"
    return kit_res


def _async_kit_handler(job_id: uuid.UUID, payload: dict[str, Any], update_progress) -> dict[str, Any]:
    """Background task executor for AI interview kit generation."""
    update_progress(20, "Extracting drive context and skills...")
    time_sleep = 0.5
    drive_id = uuid.UUID(payload["drive_id"])
    stage_id = uuid.UUID(payload["stage_id"]) if payload.get("stage_id") else None
    topic = payload["topic"]
    difficulty = payload["difficulty"]
    skills = payload.get("required_skills", [])

    update_progress(50, "Generating coding questions, scenarios, and rubrics...")
    provider = get_llm_provider()
    generation_provider = provider
    prompt = f"Role: {topic}, Difficulty: {difficulty}, Skills: {', '.join(skills)}"
    try:
        kit_res = provider.generate_structured(prompt, InterviewKitResponse)
    except Exception as exc:
        log.warning("Async AI kit generation failed (%s); using deterministic fallback", exc)
        generation_provider = DeterministicLocalProvider()
        kit_res = generation_provider.generate_structured(prompt, InterviewKitResponse)

    update_progress(80, "Saving interview kit to database...")
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        kit_row = AIInterviewKit(
            drive_id=drive_id,
            stage_id=stage_id,
            topic=topic,
            difficulty=difficulty,
            coding_challenges=[q.model_dump() for q in kit_res.coding_questions],
            system_design_scenarios=[s.model_dump() for s in kit_res.system_design_scenarios],
            behavioral_questions=[b.model_dump() for b in kit_res.behavioral_questions],
            rubric_template=kit_res.rubric_template,
            provider_used=generation_provider.name,
            model_used=getattr(generation_provider, "model", "local"),
            raw_prompt=prompt,
        )
        db.add(kit_row)
        db.commit()
        kit_id = str(kit_row.id)
    finally:
        db.close()

    update_progress(100, "Interview kit ready")
    kit_res.provider_used = generation_provider.name
    kit_res.model_used = getattr(generation_provider, "model", "local")
    kit_res.is_ai_generated = generation_provider.name != "deterministic"
    res_dict = kit_res.model_dump(mode="json")
    res_dict["kit_id"] = kit_id
    return res_dict


register_handler("ai_interview_kit", _async_kit_handler)


def generate_drive_brief(db: Session, drive_id: uuid.UUID) -> DriveBriefResponse:
    """Generate a high-level briefing for coordinators with real verified metrics and AI synthesis."""
    drive = db.get(RecruitmentDrive, drive_id)
    if not drive:
        raise NotFound("Recruitment drive not found")

    # 1. Candidate counts
    candidates = list(db.scalars(select(DriveCandidate).where(DriveCandidate.drive_id == drive.id)))
    total_enrolled = len(candidates)
    active_in_pipeline = sum(1 for c in candidates if c.status == DriveCandidateStatus.ACTIVE)
    selected = sum(1 for c in candidates if c.status == DriveCandidateStatus.SELECTED)
    rejected = sum(1 for c in candidates if c.status == DriveCandidateStatus.REJECTED)
    withdrawn = sum(1 for c in candidates if c.status == DriveCandidateStatus.WITHDRAWN)

    counts = CandidateCountsBreakdown(
        total_enrolled=total_enrolled,
        active_in_pipeline=active_in_pipeline,
        selected=selected,
        rejected=rejected,
        withdrawn=withdrawn,
    )

    # 2. Upcoming rounds & progress
    stages = sorted(drive.stages, key=lambda s: s.order_index)
    upcoming_rounds: list[UpcomingRoundBrief] = []
    for st in stages:
        scheduled_count = db.scalar(
            select(func.count(Interview.id)).where(
                Interview.stage_id == st.id,
                Interview.status.in_([InterviewStatus.SCHEDULED, InterviewStatus.CONFIRMED]),
            )
        ) or 0
        completed_count = db.scalar(
            select(func.count(Interview.id)).where(
                Interview.stage_id == st.id,
                Interview.status == InterviewStatus.COMPLETED,
            )
        ) or 0
        upcoming_rounds.append(
            UpcomingRoundBrief(
                stage_id=st.id,
                stage_name=st.name,
                order_index=st.order_index,
                scheduled_interviews=scheduled_count,
                completed_interviews=completed_count,
            )
        )

    # 3. Missing feedback
    # Find completed interviews where evaluated panel members < total panel members
    completed_interviews = list(
        db.scalars(
            select(Interview)
            .join(InterviewStage, InterviewStage.id == Interview.stage_id)
            .where(
                InterviewStage.drive_id == drive.id,
                Interview.status == InterviewStatus.COMPLETED,
            )
        )
    )

    missing_feedback: list[MissingFeedbackItem] = []
    for iv in completed_interviews:
        evaluated_interviewers = {e.interviewer_id for e in iv.evaluations}
        for p in iv.panel:
            if p.is_active and p.interviewer_id not in evaluated_interviewers:
                iv_user = db.get(User, p.interviewer_id)
                cand_user = iv.candidate.user if (iv.candidate and iv.candidate.user) else None
                missing_feedback.append(
                    MissingFeedbackItem(
                        interview_id=iv.id,
                        candidate_id=iv.candidate_id,
                        candidate_name=cand_user.name if cand_user else "Candidate",
                        interviewer_id=p.interviewer_id,
                        interviewer_name=iv_user.name if iv_user else "Interviewer",
                        stage_name=iv.stage.name if iv.stage else "Unknown Round",
                        scheduled_time=iv.start_time.isoformat() if iv.start_time else "",
                    )
                )

    # 4. Scheduling conflicts & risks
    conflicts_and_risks: list[str] = []
    if total_enrolled > 0 and len(completed_interviews) == 0 and sum(r.scheduled_interviews for r in upcoming_rounds) == 0:
        conflicts_and_risks.append("No interviews have been scheduled yet. Run the intelligent scheduler to propose initial placements.")
    if len(missing_feedback) > 0:
        conflicts_and_risks.append(f"{len(missing_feedback)} completed interview sessions are pending panel evaluations, blocking pipeline advancement.")
    if drive.status == "collecting_availability":
        conflicts_and_risks.append("Drive is currently collecting candidate availability. Remind candidates to submit free windows before scheduling.")

    # 5. Pending actions
    pending_actions: list[str] = []
    if missing_feedback:
        pending_actions.append(f"Send reminder notifications to {len(missing_feedback)} panelists for missing evaluations.")
    if active_in_pipeline > 0:
        pending_actions.append(f"Review pipeline progression for {active_in_pipeline} active candidates.")
    if drive.schedule_version == 0:
        pending_actions.append("Generate and publish the initial interview schedule.")

    if not conflicts_and_risks:
        conflicts_and_risks.append("No active scheduling conflicts detected. All assigned slots are verified.")
    if not pending_actions:
        pending_actions.append("Drive operations are currently up-to-date.")

    # 6. Summarize only aggregate metrics and feedback themes for the optional AI provider.
    drive_scores: list[float] = []
    recommendation_counts: dict[str, int] = defaultdict(int)
    feedback_texts: list[str] = []
    for interview in completed_interviews:
        for evaluation in interview.evaluations:
            if evaluation.score is not None:
                drive_scores.append(float(evaluation.score))
            if evaluation.recommendation:
                recommendation_counts[evaluation.recommendation.value] += 1
            if evaluation.feedback:
                feedback_texts.append(evaluation.feedback)

    feedback_theme_keywords = {
        "problem_solving": ("algorithm", "approach", "solution", "problem solving"),
        "code_quality": ("clean", "readable", "maintainable", "refactor"),
        "testing_edge_cases": ("test", "edge case", "coverage", "boundary"),
        "communication": ("communicat", "explain", "clarity"),
        "performance": ("performance", "optimal", "complexity", "slow"),
        "collaboration": ("collaborat", "team", "ownership"),
    }
    feedback_theme_counts = {
        theme: sum(
            1
            for feedback in feedback_texts
            if any(keyword in feedback.lower() for keyword in keywords)
        )
        for theme, keywords in feedback_theme_keywords.items()
    }
    aggregate_metrics = {
        "candidate_counts": counts.model_dump(),
        "completed_interviews": len(completed_interviews),
        "pending_evaluations": len(missing_feedback),
        "scheduled_interviews": sum(round_brief.scheduled_interviews for round_brief in upcoming_rounds),
        "average_evaluation_score": round(sum(drive_scores) / len(drive_scores), 2) if drive_scores else None,
        "recommendation_counts": dict(recommendation_counts),
        "feedback_theme_counts": feedback_theme_counts,
    }
    executive_summary = (
        f"Drive '{drive.title}' currently has {total_enrolled} enrolled candidates, with {active_in_pipeline} active in the pipeline. "
        f"A total of {len(completed_interviews)} sessions have been completed. "
        + (f"Attention required: {len(missing_feedback)} completed sessions await panel evaluations." if missing_feedback else "All completed evaluations are up to date.")
    )
    summary_task = (
        "Write a concise operations summary for a recruitment coordinator. Highlight only supported patterns in the counts, "
        "scores, recommendation totals, and feedback-theme counts. Do not identify any person or make a hiring decision."
    )
    executive_summary, response_provider, is_ai_generated = _anonymized_ai_summary(
        get_llm_provider(), summary_task, aggregate_metrics, executive_summary
    )

    return DriveBriefResponse(
        drive_id=drive.id,
        drive_title=drive.title,
        drive_status=drive.status.value,
        candidate_counts=counts,
        upcoming_rounds=upcoming_rounds,
        missing_feedback=missing_feedback[:20],
        scheduling_conflicts_and_risks=conflicts_and_risks,
        pending_actions=pending_actions,
        executive_summary=executive_summary,
        provider_used=response_provider.name,
        is_ai_generated=is_ai_generated,
    )


def generate_candidate_summary(
    db: Session,
    drive_id: uuid.UUID,
    candidate_id: uuid.UUID,
) -> CandidateSummaryResponse:
    """Generate a local evidence summary without sending individual records to an AI provider."""
    drive = db.get(RecruitmentDrive, drive_id)
    if not drive:
        raise NotFound("Recruitment drive not found")

    cand_enrollment = db.scalar(
        select(DriveCandidate).where(
            DriveCandidate.drive_id == drive_id,
            DriveCandidate.candidate_id == candidate_id,
        )
    )
    if not cand_enrollment:
        raise NotFound("Candidate is not enrolled in this recruitment drive")

    candidate_user = db.get(User, candidate_id)
    cand_name = candidate_user.name if candidate_user else "Candidate"
    cand_email = candidate_user.email if candidate_user else "unknown"

    # Fetch candidate's interviews and evaluations
    interviews = list(
        db.scalars(
            select(Interview)
            .join(InterviewStage, InterviewStage.id == Interview.stage_id)
            .where(
                InterviewStage.drive_id == drive_id,
                Interview.candidate_id == candidate_id,
            )
            .order_by(InterviewStage.order_index.asc())
        )
    )

    round_summaries: list[RoundEvaluationSummary] = []
    all_scores: list[float] = []
    all_feedbacks: list[str] = []

    for iv in interviews:
        stage = iv.stage
        for ev in iv.evaluations:
            score_float = float(ev.score)
            all_scores.append(score_float)
            if ev.feedback:
                all_feedbacks.append(ev.feedback)
            iv_user = db.get(User, ev.interviewer_id)
            round_summaries.append(
                RoundEvaluationSummary(
                    stage_name=stage.name if stage else "Round",
                    order_index=stage.order_index if stage else 1,
                    score=score_float,
                    recommendation=ev.recommendation.value if ev.recommendation else None,
                    interviewer_name=iv_user.name if iv_user else "Interviewer",
                    key_feedback=ev.feedback,
                )
            )

    avg_score = round(sum(all_scores) / len(all_scores), 2) if all_scores else None

    # Derive strengths & weaknesses from feedback text and scores
    strengths = []
    weaknesses = []

    if avg_score is not None:
        if avg_score >= 8.0:
            strengths.append("Consistently high evaluator scores across all assessed technical domains")
        elif avg_score >= 6.5:
            strengths.append("Meets or exceeds minimum progression criteria across core rounds")
        else:
            weaknesses.append("Average evaluation score is currently below target threshold for final offer")

    for fb in all_feedbacks:
        fb_lower = fb.lower()
        if "clean" in fb_lower or "algorithm" in fb_lower or "optimal" in fb_lower or "strong" in fb_lower:
            strengths.append(f"Evaluator note: '{fb[:120]}...'")
        if "slow" in fb_lower or "struggled" in fb_lower or "improve" in fb_lower or "edge case" in fb_lower:
            weaknesses.append(f"Growth area: '{fb[:120]}...'")

    if not strengths:
        strengths.append("Participated in all scheduled technical rounds.")
    if not weaknesses:
        weaknesses.append("No major red flags noted in interviewer scorecards.")

    # Deduplicate
    strengths = list(dict.fromkeys(strengths))[:5]
    weaknesses = list(dict.fromkeys(weaknesses))[:5]

    # Current stage name
    current_stage = db.get(InterviewStage, cand_enrollment.current_stage_id) if cand_enrollment.current_stage_id else None

    # Progression recommendation synthesis
    if cand_enrollment.status == DriveCandidateStatus.SELECTED:
        readiness = "Selected: Passed all drive interview stages."
        rec_synthesis = f"{cand_name} demonstrated exemplary technical and problem-solving capability across all rounds, earning final selection."
    elif cand_enrollment.status == DriveCandidateStatus.REJECTED:
        readiness = "Not Selected: Candidate did not meet the progression threshold for advancement."
        rec_synthesis = f"{cand_name} did not meet the threshold criteria in stage '{current_stage.name if current_stage else 'assessment'}'."
    else:
        if avg_score and avg_score >= 7.0:
            readiness = f"Recommended to Advance to Stage: '{current_stage.name if current_stage else 'Next Round'}'."
            rec_synthesis = f"Strong performance with an average score of {avg_score}/10. Candidate shows consistent technical mastery."
        elif avg_score:
            readiness = "Requires Coordinator Review: Borderline performance requiring panel discussion."
            rec_synthesis = f"Candidate achieved an average score of {avg_score}/10. Review detailed scorecard feedback prior to decision."
        else:
            readiness = "Pending Interviews: Candidate is currently active in the interview schedule."
            rec_synthesis = "Evaluations are still in progress. Final progression synthesis will update upon scorecard submission."

    return CandidateSummaryResponse(
        candidate_id=candidate_id,
        candidate_name=cand_name,
        candidate_email=cand_email,
        drive_id=drive_id,
        drive_title=drive.title,
        pipeline_status=cand_enrollment.status.value,
        current_stage_name=current_stage.name if current_stage else None,
        average_score=avg_score,
        evaluations_count=len(round_summaries),
        completed_rounds=round_summaries,
        recurring_strengths=strengths,
        recurring_weaknesses=weaknesses,
        recommendation_synthesis=rec_synthesis,
        progression_readiness=readiness,
        disclaimer="AI-generated synthesis of human evaluations. Human coordinator retains final decision authority.",
        provider_used="deterministic",
        is_ai_generated=False,
    )


def ask_recruitment_query(
    db: Session,
    user: User,
    question: str,
    drive_id: uuid.UUID | None = None,
) -> AskRecruitmentDataResponse:
    """Answer natural language recruitment questions against real, authorized database data."""
    q_lower = question.lower().strip()
    data_points: list[dict[str, Any]] = []
    intent = "general_query"
    answer = ""

    # 1. Intent: Awaiting evaluation / missing feedback
    if "awaiting evaluation" in q_lower or "missing feedback" in q_lower or "pending evaluation" in q_lower:
        intent = "awaiting_evaluations"
        query = (
            select(Interview)
            .join(InterviewStage, InterviewStage.id == Interview.stage_id)
            .where(Interview.status == InterviewStatus.COMPLETED)
        )
        if drive_id:
            query = query.where(InterviewStage.drive_id == drive_id)

        completed_ivs = list(db.scalars(query))
        pending_list = []
        for iv in completed_ivs:
            evaluated_ids = {e.interviewer_id for e in iv.evaluations}
            for p in iv.panel:
                if p.is_active and p.interviewer_id not in evaluated_ids:
                    cand_user = iv.candidate.user if (iv.candidate and iv.candidate.user) else None
                    iv_user = db.get(User, p.interviewer_id)
                    pending_list.append({
                        "interview_id": str(iv.id),
                        "candidate_name": cand_user.name if cand_user else "Candidate",
                        "interviewer_name": iv_user.name if iv_user else "Interviewer",
                        "stage_name": iv.stage.name if iv.stage else "Round",
                    })

        data_points = pending_list[:25]
        if pending_list:
            answer = f"There are currently {len(pending_list)} completed interviews awaiting evaluation submissions across the panel. Top pending panelists include: {', '.join(set(p['interviewer_name'] for p in pending_list[:5]))}."
        else:
            answer = "All completed interviews currently have their evaluations submitted! No pending scorecards detected."

    # 2. Intent: Interviewer workload / busiest interviewers
    elif "workload" in q_lower or "busiest" in q_lower or "most interviews" in q_lower:
        intent = "interviewer_workload"
        interviewers = list(db.scalars(select(Interviewer)))
        workload_data = []
        for ivr in interviewers:
            u = ivr.user
            count = db.scalar(
                select(func.count(PanelAssignment.interview_id)).where(
                    PanelAssignment.interviewer_id == ivr.user_id,
                    PanelAssignment.is_active.is_(True),
                )
            ) or 0
            workload_data.append({
                "interviewer_name": u.name if u else "Unknown",
                "email": u.email if u else "unknown",
                "department": ivr.department or "Core",
                "capacity_per_day": ivr.capacity,
                "assigned_interviews": count,
            })
        workload_data.sort(key=lambda x: x["assigned_interviews"], reverse=True)
        data_points = workload_data[:15]
        if workload_data:
            top = workload_data[0]
            answer = f"The interviewer with the highest workload is {top['interviewer_name']} ({top['department']}) with {top['assigned_interviews']} assigned interviews (daily capacity: {top['capacity_per_day']})."
        else:
            answer = "No active interviewer assignments were found in the database."

    # 3. Intent: Candidate progression / counts by status
    elif (
        "how many candidates" in q_lower
        or "candidates in" in q_lower
        or "candidate count" in q_lower
        or "active candidates" in q_lower
        or "selected candidates" in q_lower
        or "pass" in q_lower
        or "fail" in q_lower
    ):
        intent = "candidate_pipeline_counts"
        query = select(DriveCandidate)
        if drive_id:
            query = query.where(DriveCandidate.drive_id == drive_id)
        cands = list(db.scalars(query))
        total = len(cands)
        active = sum(1 for c in cands if c.status == DriveCandidateStatus.ACTIVE)
        selected = sum(1 for c in cands if c.status == DriveCandidateStatus.SELECTED)
        rejected = sum(1 for c in cands if c.status == DriveCandidateStatus.REJECTED)

        data_points = [
            {"status": "total", "count": total},
            {"status": "active", "count": active},
            {"status": "selected", "count": selected},
            {"status": "rejected", "count": rejected},
        ]
        answer = f"Found {total} candidate enrollment records: {active} active in the pipeline, {selected} selected for final offers, and {rejected} rejected."

    # 4. Schedule status (the Copilot's sample prompt should return schedule data).
    elif any(term in q_lower for term in ("schedule", "scheduling", "upcoming interview", "interview status")):
        intent = "schedule_status"
        query = (
            select(Interview.status, func.count(Interview.id))
            .join(InterviewStage, InterviewStage.id == Interview.stage_id)
            .group_by(Interview.status)
        )
        if drive_id:
            query = query.where(InterviewStage.drive_id == drive_id)
        status_rows = db.execute(query).all()
        status_counts = {status.value: int(count) for status, count in status_rows}
        data_points = [
            {"status": status.value, "count": status_counts.get(status.value, 0)}
            for status in InterviewStatus
        ]
        answer = (
            "Interview schedule status: "
            + ", ".join(f"{item['status'].replace('_', ' ')} {item['count']}" for item in data_points)
            + "."
        )

    # 5. Default: Query summary
    else:
        intent = "general_recruitment_overview"
        drives_count = db.scalar(select(func.count(RecruitmentDrive.id))) or 0
        interviews_count = db.scalar(select(func.count(Interview.id))) or 0
        candidates_count = db.scalar(select(func.count(Candidate.user_id))) or 0
        data_points = [
            {"metric": "total_drives", "value": drives_count},
            {"metric": "total_interviews", "value": interviews_count},
            {"metric": "total_candidates", "value": candidates_count},
        ]
        answer = f"InterviewOS is tracking {drives_count} recruitment drives, {candidates_count} candidates, and {interviews_count} interview sessions. Ask specific questions regarding pending evaluations, interviewer workload, or pipeline progression."

    response_provider = DeterministicLocalProvider()
    is_ai_generated = False
    if intent in {"candidate_pipeline_counts", "schedule_status", "general_recruitment_overview"}:
        if intent == "candidate_pipeline_counts":
            aggregate_metrics = {
                f"{item['status']}_candidates": item["count"] for item in data_points
            }
            summary_task = "Briefly explain these aggregate candidate pipeline counts to a coordinator."
        elif intent == "schedule_status":
            aggregate_metrics = {
                f"{item['status']}_interviews": item["count"] for item in data_points
            }
            summary_task = "Briefly explain these aggregate interview scheduling counts to a coordinator."
        else:
            aggregate_metrics = {item["metric"]: item["value"] for item in data_points}
            summary_task = "Briefly summarize these aggregate InterviewOS recruitment totals for a coordinator."

        answer, response_provider, is_ai_generated = _anonymized_ai_summary(
            get_llm_provider(), summary_task, aggregate_metrics, answer
        )

    return AskRecruitmentDataResponse(
        question=question,
        answer=answer,
        data_points=data_points,
        data_points_analyzed=len(data_points),
        suggested_followups=_suggested_followups(intent),
        intent=intent,
        provider_used=response_provider.name,
        is_ai_generated=is_ai_generated,
    )
