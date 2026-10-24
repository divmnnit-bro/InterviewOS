"""Checks that PostgreSQL itself rejects double bookings.

Needs a real PostgreSQL with the schema applied:
    docker compose up -d postgres          (from the repo root)
    alembic upgrade head             (from backend/)
    pytest tests/test_db_constraints.py

If the database is unreachable or not migrated, every test here is skipped.
Each test runs inside a transaction that is rolled back, so nothing persists.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Candidate,
    Interview,
    Interviewer,
    InterviewStage,
    InterviewStatus,
    PanelAssignment,
    RecruitmentDrive,
    Room,
    StageType,
    User,
    UserRole,
)

T0 = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
HALF_HOUR = timedelta(minutes=30)


@pytest.fixture()
def session():
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 3})
    try:
        connection = engine.connect()
    except OperationalError:
        pytest.skip("PostgreSQL is not reachable at DATABASE_URL")
    ready = inspect(connection).has_table("interviews")
    connection.rollback()
    if not ready:
        connection.close()
        pytest.skip("Schema not applied: run `alembic upgrade head` first")

    transaction = connection.begin()
    db = Session(bind=connection, autoflush=False, expire_on_commit=False)
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def make_user(db, role):
    user = User(
        name="Test", email=f"{uuid.uuid4()}@test.example",
        hashed_password="x", role=role,
    )
    db.add(user)
    db.flush()
    return user


def make_candidate(db):
    user = make_user(db, UserRole.CANDIDATE)
    db.add(Candidate(user_id=user.id))
    db.flush()
    return user.id


def make_interviewer(db):
    user = make_user(db, UserRole.INTERVIEWER)
    db.add(Interviewer(user_id=user.id, skills=["python"]))
    db.flush()
    return user.id


def make_room(db):
    room = Room(name=f"Room-{uuid.uuid4()}", capacity=4)
    db.add(room)
    db.flush()
    return room.id


@pytest.fixture()
def stage_id(session):
    drive = RecruitmentDrive(
        title="Test drive", window_start=T0, window_end=T0 + timedelta(days=5)
    )
    session.add(drive)
    session.flush()
    stage = InterviewStage(
        drive_id=drive.id, order_index=1, name="Coding",
        stage_type=StageType.CODING, duration_minutes=30,
    )
    session.add(stage)
    session.flush()
    return stage.id


def make_interview(db, stage_id, candidate_id, room_id, start=T0, status=InterviewStatus.SCHEDULED):
    interview = Interview(
        stage_id=stage_id, candidate_id=candidate_id, room_id=room_id,
        start_time=start, end_time=start + HALF_HOUR, status=status,
    )
    db.add(interview)
    db.flush()
    return interview


def test_same_room_overlap_is_rejected(session, stage_id):
    room = make_room(session)
    make_interview(session, stage_id, make_candidate(session), room)
    with pytest.raises(IntegrityError):
        make_interview(session, stage_id, make_candidate(session), room, start=T0 + timedelta(minutes=15))


def test_back_to_back_in_same_room_is_allowed(session, stage_id):
    room = make_room(session)
    make_interview(session, stage_id, make_candidate(session), room)
    make_interview(session, stage_id, make_candidate(session), room, start=T0 + HALF_HOUR)


def test_same_candidate_overlap_is_rejected(session, stage_id):
    candidate = make_candidate(session)
    make_interview(session, stage_id, candidate, make_room(session))
    with pytest.raises(IntegrityError):
        make_interview(session, stage_id, candidate, make_room(session), start=T0 + timedelta(minutes=10))


def test_cancelled_interview_frees_its_slot(session, stage_id):
    room = make_room(session)
    make_interview(session, stage_id, make_candidate(session), room, status=InterviewStatus.CANCELLED)
    make_interview(session, stage_id, make_candidate(session), room)


def test_same_interviewer_overlap_is_rejected(session, stage_id):
    interviewer = make_interviewer(session)
    first = make_interview(session, stage_id, make_candidate(session), make_room(session))
    second = make_interview(session, stage_id, make_candidate(session), make_room(session))
    session.add(PanelAssignment(
        interview_id=first.id, interviewer_id=interviewer,
        start_time=first.start_time, end_time=first.end_time,
    ))
    session.flush()
    session.add(PanelAssignment(
        interview_id=second.id, interviewer_id=interviewer,
        start_time=second.start_time, end_time=second.end_time,
    ))
    with pytest.raises(IntegrityError):
        session.flush()


def test_panel_slot_must_match_the_interview(session, stage_id):
    interview = make_interview(session, stage_id, make_candidate(session), make_room(session))
    session.add(PanelAssignment(
        interview_id=interview.id, interviewer_id=make_interviewer(session),
        start_time=interview.start_time,
        end_time=interview.end_time + timedelta(hours=1),  # wrong on purpose
    ))
    with pytest.raises(IntegrityError):
        session.flush()


def test_moving_an_interview_moves_its_panel_rows(session, stage_id):
    interview = make_interview(session, stage_id, make_candidate(session), make_room(session))
    interviewer = make_interviewer(session)
    session.add(PanelAssignment(
        interview_id=interview.id, interviewer_id=interviewer,
        start_time=interview.start_time, end_time=interview.end_time,
    ))
    session.flush()

    new_start = T0 + timedelta(hours=3)
    session.execute(
        update(Interview).where(Interview.id == interview.id)
        .values(start_time=new_start, end_time=new_start + HALF_HOUR)
    )
    moved = session.execute(
        select(PanelAssignment.start_time, PanelAssignment.end_time)
        .where(PanelAssignment.interview_id == interview.id)
    ).one()
    assert moved == (new_start, new_start + HALF_HOUR)


def test_idempotency_key_cannot_be_reused(session, stage_id):
    key = uuid.uuid4().hex
    first = make_interview(session, stage_id, make_candidate(session), make_room(session))
    first.idempotency_key = key
    session.flush()
    second = make_interview(
        session, stage_id, make_candidate(session), make_room(session), start=T0 + timedelta(hours=2)
    )
    second.idempotency_key = key
    with pytest.raises(IntegrityError):
        session.flush()
