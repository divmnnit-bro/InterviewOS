from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_coordinator
from app.db.database import get_db
from app.models import (
    Candidate,
    DriveCandidate,
    DriveCandidateStatus,
    DriveStatus,
    Interview,
    InterviewStage,
    RecruitmentDrive,
    User,
    InterviewStatus,
)
from app.models.stage import DEFAULT_PASS_RULE
from app.schemas.drive import (
    DriveCreate,
    DriveInterviewDetailOut,
    DriveOut,
    DriveUpdate,
    EnrollmentOut,
    EnrollRequest,
    PanelMemberOut,
    StageCreate,
    StageOut,
    StageUpdate,
)
from app.services.scheduling import get_drive

router = APIRouter(prefix="/drives", tags=["drives"], dependencies=[Depends(require_coordinator)])

# The window and the stages can only change before a schedule exists.
_EDITABLE = (DriveStatus.DRAFT, DriveStatus.COLLECTING_AVAILABILITY)


def _require_editable(drive: RecruitmentDrive, what: str) -> None:
    if drive.status not in _EDITABLE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{what} cannot be changed once the drive is {drive.status.value}",
        )


def _commit(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message)


# ---------------------------------------------------------------- drives


@router.post("", response_model=DriveOut, status_code=status.HTTP_201_CREATED)
def create_drive(body: DriveCreate, db: Session = Depends(get_db),
                 user: User = Depends(require_coordinator)) -> RecruitmentDrive:
    drive = RecruitmentDrive(**body.model_dump(), created_by=user.id, status=DriveStatus.DRAFT)
    db.add(drive)
    db.commit()
    return drive


@router.get("", response_model=list[DriveOut])
def list_drives(db: Session = Depends(get_db)) -> list[RecruitmentDrive]:
    return list(db.scalars(select(RecruitmentDrive).order_by(RecruitmentDrive.window_start.desc())))


@router.get("/{drive_id}", response_model=DriveOut)
def read_drive(drive_id: uuid.UUID, db: Session = Depends(get_db)) -> RecruitmentDrive:
    return get_drive(db, drive_id)


@router.patch("/{drive_id}", response_model=DriveOut)
def update_drive(drive_id: uuid.UUID, body: DriveUpdate, db: Session = Depends(get_db)) -> RecruitmentDrive:
    drive = get_drive(db, drive_id)
    changes = body.model_dump(exclude_unset=True)
    if {"window_start", "window_end", "timezone", "slot_minutes",
        "interviewer_buffer_minutes", "min_round_gap_minutes"} & changes.keys():
        _require_editable(drive, "the drive window, timezone and scheduling rules")
    if "status" in changes and changes["status"] in _EDITABLE and drive.status not in _EDITABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "a drive with a published schedule cannot go back to draft")
    for k, v in changes.items():
        if v is None and k != "description":
            continue
        setattr(drive, k, v)
    if drive.window_end <= drive.window_start:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "window_end must be after window_start")
    db.commit()
    return drive


# ---------------------------------------------------------------- stages


@router.post("/{drive_id}/stages", response_model=StageOut, status_code=status.HTTP_201_CREATED)
def add_stage(drive_id: uuid.UUID, body: StageCreate, db: Session = Depends(get_db)) -> InterviewStage:
    drive = get_drive(db, drive_id)
    _require_editable(drive, "stages")
    data = body.model_dump()
    data["rule"] = data["rule"] or dict(DEFAULT_PASS_RULE)
    stage = InterviewStage(drive_id=drive.id, **data)
    db.add(stage)
    _commit(db, "this drive already has a stage with that order or name")
    return stage


@router.get("/{drive_id}/stages", response_model=list[StageOut])
def list_stages(drive_id: uuid.UUID, db: Session = Depends(get_db)) -> list[InterviewStage]:
    return list(get_drive(db, drive_id).stages)


def _get_stage(db: Session, drive_id: uuid.UUID, stage_id: uuid.UUID) -> InterviewStage:
    stage = db.get(InterviewStage, stage_id)
    if stage is None or stage.drive_id != drive_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "stage not found")
    return stage


@router.patch("/{drive_id}/stages/{stage_id}", response_model=StageOut)
def update_stage(drive_id: uuid.UUID, stage_id: uuid.UUID, body: StageUpdate,
                 db: Session = Depends(get_db)) -> InterviewStage:
    _require_editable(get_drive(db, drive_id), "stages")
    stage = _get_stage(db, drive_id, stage_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(stage, k, v)
    _commit(db, "this drive already has a stage with that order or name")
    return stage


@router.delete("/{drive_id}/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stage(drive_id: uuid.UUID, stage_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    _require_editable(get_drive(db, drive_id), "stages")
    stage = _get_stage(db, drive_id, stage_id)
    if db.scalar(select(Interview.id).where(Interview.stage_id == stage_id).limit(1)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "this stage already has interviews")
    db.delete(stage)
    _commit(db, "this stage is still in use")


# ---------------------------------------------------------------- enrolment


@router.post("/{drive_id}/candidates", response_model=list[EnrollmentOut],
             status_code=status.HTTP_201_CREATED)
def enroll(drive_id: uuid.UUID, body: EnrollRequest, db: Session = Depends(get_db)) -> list[DriveCandidate]:
    drive = get_drive(db, drive_id)
    ids = set(body.candidate_ids)
    found = set(db.scalars(select(Candidate.user_id).where(Candidate.user_id.in_(ids))))
    if found != ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"message": "unknown candidate ids", "ids": sorted(str(i) for i in ids - found)},
        )
    already = set(db.scalars(
        select(DriveCandidate.candidate_id).where(
            DriveCandidate.drive_id == drive.id, DriveCandidate.candidate_id.in_(ids)
        )
    ))
    first_stage = drive.stages[0].id if drive.stages else None
    created = [
        DriveCandidate(drive_id=drive.id, candidate_id=cid,
                       status=DriveCandidateStatus.ACTIVE, current_stage_id=first_stage)
        for cid in sorted(ids - already, key=str)
    ]
    db.add_all(created)
    _commit(db, "could not enroll those candidates")
    return created


@router.get("/{drive_id}/candidates", response_model=list[EnrollmentOut])
def list_enrollments(drive_id: uuid.UUID, db: Session = Depends(get_db)) -> list[DriveCandidate]:
    get_drive(db, drive_id)
    return list(db.scalars(select(DriveCandidate).where(DriveCandidate.drive_id == drive_id)))


@router.delete("/{drive_id}/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw(drive_id: uuid.UUID, candidate_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    """Marks the candidate withdrawn (history is kept). Their existing interviews are not touched."""
    row = db.get(DriveCandidate, (drive_id, candidate_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "candidate is not enrolled in this drive")
    row.status = DriveCandidateStatus.WITHDRAWN
    db.commit()


@router.get("/{drive_id}/interviews", response_model=list[DriveInterviewDetailOut])
def list_drive_interviews(
    drive_id: uuid.UUID,
    status: InterviewStatus | None = None,
    db: Session = Depends(get_db),
) -> list[DriveInterviewDetailOut]:
    """Returns all interviews for a drive, optionally filtered by status."""
    get_drive(db, drive_id)
    query = (
        select(Interview)
        .join(InterviewStage, Interview.stage_id == InterviewStage.id)
        .where(InterviewStage.drive_id == drive_id)
    )
    if status is not None:
        query = query.where(Interview.status == status)

    interviews = list(db.scalars(query.order_by(Interview.start_time, Interview.id)))
    out: list[DriveInterviewDetailOut] = []
    for it in interviews:
        panel_members = [
            PanelMemberOut(id=p.interviewer.user.id, name=p.interviewer.user.name)
            for p in it.panel
            if p.is_active and p.interviewer and p.interviewer.user
        ]
        out.append(
            DriveInterviewDetailOut(
                id=it.id,
                drive_id=drive_id,
                stage_id=it.stage_id,
                stage_name=it.stage.name if it.stage else "",
                candidate_id=it.candidate_id,
                candidate_name=it.candidate.user.name if (it.candidate and it.candidate.user) else "",
                room_id=it.room_id,
                room_name=it.room.name if it.room else None,
                panel=panel_members,
                start_time=it.start_time,
                end_time=it.end_time,
                status=it.status,
                version=it.version,
            )
        )
    return out

