from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.job import Job, JobStatus

log = logging.getLogger(__name__)

# Registered job handlers: job_type -> callable(job_id: uuid.UUID, payload: dict, update_progress: Callable)
_JOB_HANDLERS: dict[str, Callable[[uuid.UUID, dict[str, Any], Callable[[int, str], None]], dict[str, Any]]] = {}

# Background thread pool executor for processing asynchronous jobs
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="interviewos-worker")
_active_futures: dict[uuid.UUID, concurrent.futures.Future] = {}
_futures_lock = threading.Lock()


def register_handler(job_type: str, handler: Callable[[uuid.UUID, dict[str, Any], Callable[[int, str], None]], dict[str, Any]]) -> None:
    """Register an executable handler for a job type."""
    _JOB_HANDLERS[job_type] = handler


def enqueue_job(
    db: Session,
    job_type: str,
    payload: dict[str, Any],
    creator_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    max_retries: int = 3,
) -> Job:
    """Create and enqueue a background job. Idempotent if idempotency_key is provided."""
    if idempotency_key:
        existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
        if existing:
            return existing

    job = Job(
        job_type=job_type,
        status=JobStatus.QUEUED,
        creator_id=creator_id,
        payload=payload,
        max_retries=max_retries,
        idempotency_key=idempotency_key,
        progress=0,
        progress_message="Queued for processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch to background executor
    _dispatch_job(job.id)
    return job


def get_job(db: Session, job_id: uuid.UUID) -> Job | None:
    return db.get(Job, job_id)


def list_jobs(
    db: Session,
    creator_id: uuid.UUID | None = None,
    job_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[Job]:
    query = select(Job)
    if creator_id is not None:
        query = query.where(Job.creator_id == creator_id)
    if job_type is not None:
        query = query.where(Job.job_type == job_type)
    if status is not None:
        query = query.where(Job.status == status)
    return list(db.scalars(query.order_by(Job.created_at.desc()).limit(limit)))


def cancel_job(db: Session, job_id: uuid.UUID) -> bool:
    job = db.get(Job, job_id)
    if not job or job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        return False

    job.status = JobStatus.CANCELLED
    job.progress_message = "Cancelled by user"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()

    with _futures_lock:
        future = _active_futures.pop(job_id, None)
        if future and not future.done():
            future.cancel()
    return True


def _dispatch_job(job_id: uuid.UUID) -> None:
    """Submit the job to the thread pool worker."""
    def _run():
        _execute_job_runner(job_id)

    future = _executor.submit(_run)
    with _futures_lock:
        _active_futures[job_id] = future
    future.add_done_callback(lambda _: _cleanup_future(job_id))


def _cleanup_future(job_id: uuid.UUID) -> None:
    with _futures_lock:
        _active_futures.pop(job_id, None)


def _execute_job_runner(job_id: uuid.UUID) -> None:
    """Worker loop that runs a single job with retries and exponential backoff."""
    db: Session = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job or job.status == JobStatus.CANCELLED:
            return

        job_type = job.job_type
        handler = _JOB_HANDLERS.get(job_type)
        if not handler:
            job.status = JobStatus.FAILED
            job.error_message = f"No handler registered for job type: {job_type}"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.progress = 5
        job.progress_message = "Starting job processing..."
        db.commit()

        def update_progress(percent: int, message: str) -> None:
            nonlocal job
            try:
                progress_db = SessionLocal()
                p_job = progress_db.get(Job, job_id)
                if p_job and p_job.status == JobStatus.RUNNING:
                    p_job.progress = min(max(percent, 0), 100)
                    p_job.progress_message = message[:255]
                    progress_db.commit()
                progress_db.close()
            except Exception as e:
                log.debug("Failed to update job progress: %s", e)

        # Execute with retry logic
        success = False
        attempt = 0
        last_error = None

        while attempt <= job.max_retries and not success:
            attempt += 1
            try:
                result = handler(job.id, job.payload, update_progress)
                job.status = JobStatus.COMPLETED
                job.result = result
                job.progress = 100
                job.progress_message = "Job completed successfully"
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = None
                db.commit()
                success = True
                log.info("Job %s (%s) completed successfully", job.id, job_type)
            except Exception as exc:
                last_error = str(exc)
                log.warning("Job %s attempt %d failed: %s", job.id, attempt, exc)
                job.retry_count = attempt
                if attempt <= job.max_retries:
                    # Bounded exponential backoff: 2^(attempt-1) seconds, max 10s
                    backoff = min(2.0 ** (attempt - 1), 10.0)
                    job.progress_message = f"Attempt {attempt} failed, retrying in {backoff:.1f}s..."
                    db.commit()
                    time.sleep(backoff)
                else:
                    job.status = JobStatus.FAILED
                    job.error_message = f"Job failed after {attempt} attempts: {last_error}"
                    job.completed_at = datetime.now(timezone.utc)
                    db.commit()
    except Exception as exc:
        log.exception("Fatal unhandled exception processing job %s: %s", job_id, exc)
        try:
            job = db.get(Job, job_id)
            if job and job.status not in (JobStatus.COMPLETED, JobStatus.CANCELLED):
                job.status = JobStatus.FAILED
                job.error_message = f"Fatal worker error: {str(exc)}"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def recover_stale_jobs() -> int:
    """Recover jobs left running after worker/server restart."""
    db: Session = SessionLocal()
    recovered = 0
    try:
        stale_jobs = list(db.scalars(select(Job).where(Job.status == JobStatus.RUNNING)))
        for j in stale_jobs:
            if j.retry_count < j.max_retries:
                j.status = JobStatus.QUEUED
                j.progress_message = f"Resumed after server restart (attempt {j.retry_count + 1})"
                db.commit()
                _dispatch_job(j.id)
                recovered += 1
            else:
                j.status = JobStatus.FAILED
                j.error_message = "Job abandoned after server restart (max retries reached)"
                j.completed_at = datetime.now(timezone.utc)
                db.commit()
        if recovered:
            log.info("Recovered %d stale jobs from previous run", recovered)
    except Exception as exc:
        log.error("Failed to recover stale jobs: %s", exc)
    finally:
        db.close()
    return recovered
