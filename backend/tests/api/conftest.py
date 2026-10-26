"""API tests run against a real PostgreSQL (the schema relies on exclusion constraints).

    docker compose up -d postgres && alembic upgrade head && pytest tests/api

Skipped when the database is unreachable or not migrated to 0002. Every test runs inside one
outer transaction that is rolled back; the app's commits become savepoint releases.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.database import get_db
from app.main import app
from app.models import User, UserRole, UserStatus

T0 = datetime(2026, 11, 2, tzinfo=timezone.utc)  # a Monday
PASSWORD = "a-long-enough-password"


def iso(hour: int, minute: int = 0, day: int = 0) -> str:
    return (T0 + timedelta(days=day, hours=hour, minutes=minute)).isoformat()


@pytest.fixture()
def db():
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 3})
    try:
        connection = engine.connect()
    except OperationalError:
        pytest.skip("PostgreSQL is not reachable at DATABASE_URL")
    insp = inspect(connection)
    ready = insp.has_table("room_availabilities")
    connection.rollback()
    if not ready:
        connection.close()
        pytest.skip("Schema not at migration 0002: run `alembic upgrade head`")
    outer = connection.begin()
    session = Session(bind=connection, autoflush=False, expire_on_commit=False,
                      join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_user(db, email: str, role: UserRole, status: UserStatus = UserStatus.ACTIVE) -> User:
    u = User(name=email.split("@")[0], email=email, hashed_password=hash_password(PASSWORD),
             role=role, status=status)
    db.add(u)
    db.commit()
    return u


def login(client, email: str) -> dict[str, str]:
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def coordinator(db, client):
    make_user(db, "coord@example.com", UserRole.COORDINATOR)
    return login(client, "coord@example.com")


@pytest.fixture()
def drive(client, coordinator):
    """One drive, one 30-minute stage needing 'python', 2 interviewers, 1 room, 3 candidates,
    everyone free 09:00-17:00 on the first day."""
    h = coordinator
    d = client.post("/drives", headers=h, json={
        "title": "Autumn drive", "window_start": iso(0), "window_end": iso(0, day=2)}).json()
    did = d["id"]
    assert client.patch(f"/drives/{did}", headers=h, json={"status": "collecting_availability"}).status_code == 200
    r = client.post(f"/drives/{did}/stages", headers=h, json={
        "order_index": 1, "name": "Tech", "stage_type": "technical",
        "duration_minutes": 30, "panel_size": 1, "required_skills": ["python"]})
    assert r.status_code == 201, r.text
    window = {"windows": [{"start_time": iso(9), "end_time": iso(17)}]}

    for n in range(2):
        u = client.post("/users", headers=h, json={
            "name": f"iv{n}", "email": f"iv{n}@example.com", "password": PASSWORD,
            "role": "interviewer", "skills": ["python"], "capacity": 8}).json()
        assert client.put(f"/users/{u['id']}/availability", headers=h, json=window).status_code == 200

    room = client.post("/rooms", headers=h, json={"name": "R1", "capacity": 3}).json()

    cands = []
    for n in range(3):
        u = client.post("/users", headers=h, json={
            "name": f"c{n}", "email": f"c{n}@example.com", "password": PASSWORD, "role": "candidate"}).json()
        client.put(f"/users/{u['id']}/availability", headers=h, json=window)
        cands.append(u["id"])
    assert client.post(f"/drives/{did}/candidates", headers=h, json={"candidate_ids": cands}).status_code == 201
    return {"id": did, "room": room["id"], "candidates": cands, "headers": h}


@pytest.fixture()
def published(client, drive):
    h, did = drive["headers"], drive["id"]
    assert client.post(f"/drives/{did}/schedule/propose", headers=h).status_code == 200
    r = client.post(f"/drives/{did}/schedule/publish", headers=h, json={"expected_version": 0})
    assert r.status_code == 200, r.text
    return drive
