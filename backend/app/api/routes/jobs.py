from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_coordinator
from app.db.database import get_db
from app.models import User, UserRole
from app.models.job import JobStatus
from app.schemas.job import JobCancelResponse, JobOut, JobSummaryOut
from app.services import job_queue

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    job_type: Annotated[str | None, Query(description="Filter by job type")] = None,
    status_filter: Annotated[str | None, Query(alias="status", description="Filter by status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[JobOut]:
    """List asynchronous background jobs. Coordinators see all; others see their own."""
    creator_id = None if user.role == UserRole.COORDINATOR else user.id
    return job_queue.list_jobs(
        db,
        creator_id=creator_id,
        job_type=job_type,
        status=status_filter,
        limit=limit,
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job_status(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobOut:
    """Get full details and progress of a background job."""
    job = job_queue.get_job(db, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    if user.role != UserRole.COORDINATOR and job.creator_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Access denied to this job")
    return job


@router.get("/{job_id}/summary", response_model=JobSummaryOut)
def get_job_summary(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JobSummaryOut:
    """Lightweight polling endpoint returning job progress and status."""
    job = job_queue.get_job(db, job_id)
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    if user.role != UserRole.COORDINATOR and job.creator_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Access denied to this job")
    is_done = job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
    return JobSummaryOut(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        progress_message=job.progress_message,
        is_done=is_done,
    )


@router.post("/{job_id}/cancel", response_model=JobCancelResponse)
def cancel_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_coordinator),
) -> JobCancelResponse:
    """Cancel a queued or running background job."""
    success = job_queue.cancel_job(db, job_id)
    if not success:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Job cannot be cancelled (already completed, failed, or not found)",
        )
    return JobCancelResponse(
        job_id=job_id,
        cancelled=True,
        message="Job successfully cancelled",
    )
