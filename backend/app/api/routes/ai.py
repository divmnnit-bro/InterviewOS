from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_coordinator, require_staff
from app.db.database import get_db
from app.models import User
from app.schemas.ai import (
    AskRecruitmentDataRequest,
    AskRecruitmentDataResponse,
    CandidateSummaryRequest,
    CandidateSummaryResponse,
    DriveBriefRequest,
    DriveBriefResponse,
    InterviewKitRequest,
    InterviewKitDraftUpdate,
    InterviewKitResponse,
)
from app.services.ai import copilot

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/interview-kit", response_model=InterviewKitResponse, status_code=status.HTTP_200_OK)
def create_interview_kit(
    req: InterviewKitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_coordinator),
) -> InterviewKitResponse:
    """Generate structured technical questions, coding edge cases, and rubrics using AI."""
    return copilot.generate_interview_kit(db, req, actor_id=user.id)


@router.put("/interview-kits/{kit_id}", response_model=InterviewKitResponse)
def update_interview_kit_draft(
    kit_id: uuid.UUID,
    req: InterviewKitDraftUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_coordinator),
) -> InterviewKitResponse:
    """Save a coordinator-reviewed interview-kit draft before it is used."""
    return copilot.update_interview_kit_draft(db, kit_id, req, actor_id=user.id)


@router.post("/drive-brief", response_model=DriveBriefResponse, status_code=status.HTTP_200_OK)
def get_drive_brief(
    req: DriveBriefRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> DriveBriefResponse:
    """Synthesize operational drive overview, upcoming rounds, missing feedback, and risks."""
    return copilot.generate_drive_brief(db, req.drive_id)


@router.post("/candidate-summary", response_model=CandidateSummaryResponse, status_code=status.HTTP_200_OK)
def get_candidate_summary(
    req: CandidateSummaryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> CandidateSummaryResponse:
    """Synthesize multi-round candidate performance, recurring strengths, and progression readiness."""
    return copilot.generate_candidate_summary(db, req.drive_id, req.candidate_id)


@router.post("/ask", response_model=AskRecruitmentDataResponse, status_code=status.HTTP_200_OK)
def ask_recruitment_copilot(
    req: AskRecruitmentDataRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_coordinator),
) -> AskRecruitmentDataResponse:
    """Natural language queries about authorized recruitment data (e.g. pending evaluations, workload)."""
    return copilot.ask_recruitment_query(db, user, req.question, req.drive_id)
