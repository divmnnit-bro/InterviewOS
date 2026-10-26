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


def test_list_users_filters_and_profiles(client, db, coordinator):
    # Non-coordinators cannot access GET /users
    make_user(db, "cand@example.com", UserRole.CANDIDATE)
    cand_h = login(client, "cand@example.com")
    assert client.get("/users", headers=cand_h).status_code == 403
    assert client.get("/users").status_code == 401

    # Create an interviewer and candidate with profiles
    client.post("/users", headers=coordinator, json={
        "name": "Alice Interviewer", "email": "alice.iv@example.com", "password": PASSWORD,
        "role": "interviewer", "skills": ["python", "go"], "capacity": 5, "department": "Core"
    })
    client.post("/users", headers=coordinator, json={
        "name": "Bob Candidate", "email": "bob.cand@example.com", "password": PASSWORD,
        "role": "candidate", "roll_number": "CS-101", "branch": "CSE"
    })

    # Test list without filter
    res = client.get("/users", headers=coordinator)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 3

    # Test filter by role
    iv_res = client.get("/users?role=interviewer", headers=coordinator)
    assert iv_res.status_code == 200
    ivs = iv_res.json()
    assert any(u["email"] == "alice.iv@example.com" and "python" in u["skills"] and u["capacity"] == 5 for u in ivs)

    cand_res = client.get("/users?role=candidate", headers=coordinator)
    assert cand_res.status_code == 200
    cands = cand_res.json()
    assert any(u["email"] == "bob.cand@example.com" and u["roll_number"] == "CS-101" for u in cands)

    # Test search q
    q_res = client.get("/users?q=alice", headers=coordinator)
    assert q_res.status_code == 200
    assert len(q_res.json()) == 1
    assert q_res.json()[0]["email"] == "alice.iv@example.com"


def test_me_interviews_and_progress_isolation(client, db, coordinator):
    # Create candidate and interviewer
    make_user(db, "cand_prog@example.com", UserRole.CANDIDATE)
    make_user(db, "iv_prog@example.com", UserRole.INTERVIEWER)
    cand_h = login(client, "cand_prog@example.com")
    iv_h = login(client, "iv_prog@example.com")

    # 1. /me/interviews
    cand_ivs = client.get("/me/interviews", headers=cand_h)
    assert cand_ivs.status_code == 200
    assert isinstance(cand_ivs.json(), list)

    iv_ivs = client.get("/me/interviews", headers=iv_h)
    assert iv_ivs.status_code == 200
    assert isinstance(iv_ivs.json(), list)

    # 2. /me/progress (Candidates only)
    cand_prog = client.get("/me/progress", headers=cand_h)
    assert cand_prog.status_code == 200
    assert isinstance(cand_prog.json(), list)

    # Candidate progress MUST NOT leak any scores, rubrics, or feedback
    prog_json = cand_prog.json()
    for item in prog_json:
        assert "score" not in item
        assert "feedback" not in item
        assert "rubric" not in item
        assert "evaluations" not in item

    # Interviewer or coordinator cannot access /me/progress (403 Forbidden)
    assert client.get("/me/progress", headers=iv_h).status_code == 403
    assert client.get("/me/progress", headers=coordinator).status_code == 403


