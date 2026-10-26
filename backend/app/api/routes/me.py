from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models import (
    Candidate,
    DriveCandidate,
    DriveCandidateStatus,
    Interview,
    InterviewStage,
    PanelAssignment,
    RecruitmentDrive,
    User,
    UserRole,
)
from app.schemas.me import CandidateDriveProgressOut, DecidedRoundResult, MyInterviewOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/interviews", response_model=list[MyInterviewOut])
def my_interviews(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MyInterviewOut]:
    """Returns own interviews for candidates and interviewers."""
    interviews: list[Interview] = []

    if user.role == UserRole.CANDIDATE:
        interviews = list(
            db.scalars(
                select(Interview)
                .where(Interview.candidate_id == user.id)
                .order_by(Interview.start_time.asc())
            )
        )
    elif user.role == UserRole.INTERVIEWER:
        interviews = list(
            db.scalars(
                select(Interview)
                .join(PanelAssignment, PanelAssignment.interview_id == Interview.id)
                .where(
                    PanelAssignment.interviewer_id == user.id,
                    PanelAssignment.is_active.is_(True),
                )
                .order_by(Interview.start_time.asc())
            )
        )

    out: list[MyInterviewOut] = []
    for it in interviews:
        stage = it.stage
        drive = stage.drive if stage else None

        panel_names = [
            p.interviewer.user.name
            for p in it.panel
            if p.is_active and p.interviewer and p.interviewer.user
        ]

        candidate_name = (
            it.candidate.user.name
            if (it.candidate and it.candidate.user)
            else None
        )

        out.append(
            MyInterviewOut(
                id=it.id,
                drive_id=drive.id if drive else uuid.UUID(int=0),
                drive_title=drive.title if drive else "Unknown Drive",
                stage_id=it.stage_id,
                stage_name=stage.name if stage else "Unknown Stage",
                room_id=it.room_id,
                room_name=it.room.name if it.room else None,
                start_time=it.start_time,
                end_time=it.end_time,
                status=it.status,
                version=it.version,
                candidate_name=candidate_name if user.role != UserRole.CANDIDATE else None,
                panel_names=panel_names if user.role == UserRole.CANDIDATE else [],
            )
        )

    return out


@router.get("/progress", response_model=list[CandidateDriveProgressOut])
def my_progress(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CandidateDriveProgressOut]:
    """Returns candidate's enrolment status and round results ONLY (never scores or feedback)."""
    if user.role != UserRole.CANDIDATE:
        return []

    enrollments = list(
        db.scalars(
            select(DriveCandidate)
            .where(DriveCandidate.candidate_id == user.id)
        )
    )

    out: list[CandidateDriveProgressOut] = []
    for enr in enrollments:
        drive = db.get(RecruitmentDrive, enr.drive_id)
        if not drive:
            continue

        stages = sorted(drive.stages, key=lambda s: s.order_index)
        current_stage = (
            next((s for s in stages if s.id == enr.current_stage_id), stages[0])
            if stages
            else None
        )

        current_idx = current_stage.order_index if current_stage else -1
        total_stages = len(stages)

        round_results: list[DecidedRoundResult] = []
        for s in stages:
            res = None
            if enr.status == DriveCandidateStatus.SELECTED:
                if s.order_index == total_stages - 1:
                    res = "selected"
                else:
                    res = "advanced"
            elif enr.status == DriveCandidateStatus.REJECTED:
                if s.id == enr.current_stage_id:
                    res = "not_selected"
                elif s.order_index < current_idx:
                    res = "advanced"
            elif enr.status in (DriveCandidateStatus.ACTIVE, DriveCandidateStatus.WITHDRAWN):
                if s.order_index < current_idx:
                    res = "advanced"

            round_results.append(
                DecidedRoundResult(
                    stage_id=s.id,
                    stage_name=s.name,
                    order_index=s.order_index,
                    result=res,
                )
            )

        out.append(
            CandidateDriveProgressOut(
                drive_id=drive.id,
                drive_title=drive.title,
                enrolment_status=enr.status,
                current_stage_id=current_stage.id if current_stage else None,
                current_stage_name=current_stage.name if current_stage else None,
                rounds=round_results,
            )
        )

    return out
