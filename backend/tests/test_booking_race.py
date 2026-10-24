"""Race tests: simultaneous bookings from separate database connections.

These COMMIT real rows (threads cannot share a rolled-back test transaction), so they create
uniquely named data and delete it afterwards. Skipped when PostgreSQL is unreachable or not
migrated to 0003.

    docker compose up -d postgres && alembic upgrade head && pytest tests/test_booking_race.py
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, inspect, select
from sqlalchemy.exc import OperationalError

from app.core.security import BookingClaims
from app.db.database import SessionLocal, engine
from app.models import (
    Availability, Candidate, DriveCandidate, DriveStatus, Interview, Interviewer, InterviewStage,
    RecruitmentDrive, Room, StageType, User, UserRole,
)
from app.services import booking
from app.services.errors import SlotUnavailable

T0 = datetime(2026, 11, 2, tzinfo=timezone.utc)
START = T0 + timedelta(hours=9)


@pytest.fixture(autouse=True)
def _require_db():
    try:
        with engine.connect() as c:
            if "slot_minutes" not in {col["name"] for col in inspect(c).get_columns("recruitment_drives")}:
                pytest.skip("schema is not at migration 0003")
    except OperationalError:
        pytest.skip("PostgreSQL is not reachable at DATABASE_URL")


class World:
    """Committed test data: one drive, one 30-minute stage, N candidates, M interviewers, K rooms."""

    def __init__(self, *, candidates: int, interviewers: int, rooms: int, capacity: int = 8):
        tag = uuid.uuid4().hex[:8]
        self.user_ids: list[uuid.UUID] = []
        self.room_ids: list[uuid.UUID] = []
        with SessionLocal() as db:
            drive = RecruitmentDrive(title=f"race-{tag}", window_start=T0, window_end=T0 + timedelta(days=1),
                                     status=DriveStatus.PUBLISHED)
            db.add(drive)
            db.flush()
            self.drive_id = drive.id
            stage = InterviewStage(drive_id=drive.id, order_index=1, name="Tech", stage_type=StageType.TECHNICAL,
                                   duration_minutes=30, panel_size=1, required_skills=[])
            db.add(stage)
            db.flush()
            self.stage_id = stage.id
            window = (T0 + timedelta(hours=9), T0 + timedelta(hours=17))

            def user(name, role):
                u = User(name=name, email=f"{name}-{tag}@race.test", hashed_password="x", role=role)
                db.add(u)
                db.flush()
                self.user_ids.append(u.id)
                db.add(Availability(owner_id=u.id, start_time=window[0], end_time=window[1]))
                return u

            for n in range(interviewers):
                u = user(f"iv{n}", UserRole.INTERVIEWER)
                u.interviewer = Interviewer(skills=[], capacity=capacity)
            self.candidates: list[uuid.UUID] = []
            for n in range(candidates):
                u = user(f"c{n}", UserRole.CANDIDATE)
                u.candidate = Candidate()
                db.flush()
                db.add(DriveCandidate(drive_id=drive.id, candidate_id=u.id, current_stage_id=stage.id))
                self.candidates.append(u.id)
            for n in range(rooms):
                r = Room(name=f"race-room-{tag}-{n}", capacity=3)
                db.add(r)
                db.flush()
                self.room_ids.append(r.id)
            db.commit()

    def claims(self, i: int) -> BookingClaims:
        return BookingClaims(self.candidates[i], self.drive_id, self.stage_id)

    def interviews(self) -> list[Interview]:
        with SessionLocal() as db:
            return list(db.scalars(select(Interview).where(Interview.stage_id == self.stage_id)))

    def cleanup(self):
        with SessionLocal() as db:
            db.execute(delete(Interview).where(Interview.stage_id == self.stage_id))
            db.execute(delete(RecruitmentDrive).where(RecruitmentDrive.id == self.drive_id))
            db.execute(delete(Room).where(Room.id.in_(self.room_ids)))
            db.execute(delete(User).where(User.id.in_(self.user_ids)))
            db.commit()


@pytest.fixture()
def world_factory():
    made: list[World] = []

    def make(**kw) -> World:
        w = World(**kw)
        made.append(w)
        return w

    yield make
    for w in made:
        w.cleanup()


def race(jobs):
    """Run each (claims, start, key) at the same moment, one connection each. Returns outcomes in order."""
    barrier = threading.Barrier(len(jobs))
    out: list = [None] * len(jobs)

    def run(i, claims, start, key):
        with SessionLocal() as db:
            barrier.wait()
            try:
                out[i] = booking.book(db, claims, start, key)
            except Exception as exc:  # noqa: BLE001 - the test inspects the type
                out[i] = exc

    threads = [threading.Thread(target=run, args=(i, *j)) for i, j in enumerate(jobs)]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    assert all(o is not None for o in out), "a booking thread hung"
    return out


@pytest.mark.parametrize("round_", range(3))
def test_two_candidates_one_room_one_slot(world_factory, round_):
    w = world_factory(candidates=2, interviewers=2, rooms=1)
    out = race([(w.claims(0), START, "key-candidate-0"), (w.claims(1), START, "key-candidate-1")])
    wins = [o for o in out if isinstance(o, tuple)]
    losses = [o for o in out if isinstance(o, SlotUnavailable)]
    assert len(wins) == 1 and len(losses) == 1, out
    assert len(w.interviews()) == 1


@pytest.mark.parametrize("round_", range(3))
def test_one_interviewer_two_rooms_one_slot(world_factory, round_):
    w = world_factory(candidates=2, interviewers=1, rooms=2)
    out = race([(w.claims(0), START, "key-candidate-0"), (w.claims(1), START, "key-candidate-1")])
    assert sum(isinstance(o, tuple) for o in out) == 1 and sum(isinstance(o, SlotUnavailable) for o in out) == 1, out


@pytest.mark.parametrize("round_", range(3))
def test_daily_limit_cannot_be_beaten_by_booking_different_slots_at_once(world_factory, round_):
    """No database constraint covers the daily limit; the interviewer row lock plus the recheck do."""
    w = world_factory(candidates=2, interviewers=1, rooms=2, capacity=1)
    out = race([(w.claims(0), START, "key-candidate-0"),
                (w.claims(1), START + timedelta(hours=3), "key-candidate-1")])
    assert sum(isinstance(o, tuple) for o in out) == 1 and sum(isinstance(o, SlotUnavailable) for o in out) == 1, out
    assert len(w.interviews()) == 1


def test_same_idempotency_key_sent_twice_at_once_makes_one_interview(world_factory):
    w = world_factory(candidates=1, interviewers=1, rooms=1)
    out = race([(w.claims(0), START, "same-key-12345"), (w.claims(0), START, "same-key-12345")])
    assert all(isinstance(o, tuple) for o in out), out
    assert sorted(created for _, created in out) == [False, True]
    assert out[0][0].id == out[1][0].id and len(w.interviews()) == 1


def test_a_second_key_for_the_same_round_is_refused(world_factory):
    w = world_factory(candidates=1, interviewers=1, rooms=1)
    out = race([(w.claims(0), START, "first-key-12345"), (w.claims(0), START + timedelta(hours=1), "second-key-1234")])
    assert sum(isinstance(o, tuple) for o in out) == 1 and len(w.interviews()) == 1, out
