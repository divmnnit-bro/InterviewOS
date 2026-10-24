from app.models import UserRole, UserStatus

from .conftest import PASSWORD, login, make_user


def test_login_failures_look_identical(client, db):
    make_user(db, "a@example.com", UserRole.CANDIDATE)
    wrong = client.post("/auth/login", json={"email": "a@example.com", "password": "nope"})
    unknown = client.post("/auth/login", json={"email": "ghost@example.com", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_suspended_user_cannot_login_or_use_old_token(client, db):
    u = make_user(db, "s@example.com", UserRole.CANDIDATE)
    headers = login(client, "s@example.com")
    assert client.get("/auth/me", headers=headers).status_code == 200
    u.status = UserStatus.SUSPENDED
    db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401  # role/status re-read per request
    assert client.post("/auth/login", json={"email": "s@example.com", "password": PASSWORD}).status_code == 401


def test_no_token_is_401_and_wrong_role_is_403(client, db):
    assert client.get("/drives").status_code == 401
    make_user(db, "c@example.com", UserRole.CANDIDATE)
    assert client.get("/drives", headers=login(client, "c@example.com")).status_code == 403


def test_public_register_always_makes_a_candidate(client):
    r = client.post("/auth/register", json={
        "name": "Eve", "email": "Eve@Example.com", "password": PASSWORD, "role": "coordinator"})
    assert r.status_code == 201
    assert r.json()["role"] == "candidate"          # an extra "role" field is ignored
    assert r.json()["email"] == "eve@example.com"   # emails are stored lowercase
    dup = client.post("/auth/register", json={"name": "Eve", "email": "eve@example.com", "password": PASSWORD})
    assert dup.status_code == 409


def test_only_coordinators_create_interviewers(client, db, coordinator):
    body = {"name": "Iv", "email": "iv@example.com", "password": PASSWORD, "role": "interviewer",
            "skills": ["python"], "capacity": 3}
    assert client.post("/users", json=body).status_code == 401
    assert client.post("/users", json=body, headers=coordinator).status_code == 201
