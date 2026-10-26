from __future__ import annotations

import time
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models import UserRole
from app.services import job_queue

from .conftest import login, make_user


def test_job_enqueue_and_poll(client, db, coordinator):
    h = coordinator
    # Enqueue a dummy job
    job_queue.register_handler("test_echo", lambda jid, payload, prog: {"echo": payload["msg"]})

    job = job_queue.enqueue_job(db, "test_echo", {"msg": "hello world"}, idempotency_key="key-1")
    assert job.status in ("queued", "running", "completed")

    r = client.get(f"/jobs/{job.id}", headers=h)
    assert r.status_code == 200
    assert r.json()["job_type"] == "test_echo"

    # Poll summary
    sr = client.get(f"/jobs/{job.id}/summary", headers=h)
    assert sr.status_code == 200
    assert "progress" in sr.json()

    # Idempotent enqueue returns the same job
    job2 = job_queue.enqueue_job(db, "test_echo", {"msg": "hello world 2"}, idempotency_key="key-1")
    assert job2.id == job.id


def test_job_cancellation(client, db, coordinator):
    h = coordinator
    job_queue.register_handler("test_sleep", lambda jid, payload, prog: time.sleep(10) or {})

    job = job_queue.enqueue_job(db, "test_sleep", {})
    r = client.post(f"/jobs/{job.id}/cancel", headers=h)
    assert r.status_code == 200
    assert r.json()["cancelled"] is True


def test_jobs_access_isolation(client, db):
    cand1 = make_user(db, "jcand1@example.com", UserRole.CANDIDATE)
    cand2 = make_user(db, "jcand2@example.com", UserRole.CANDIDATE)
    h1 = login(client, "jcand1@example.com")
    h2 = login(client, "jcand2@example.com")

    job = job_queue.enqueue_job(db, "test_priv", {}, creator_id=cand1.id)

    # cand1 can see own job
    assert client.get(f"/jobs/{job.id}", headers=h1).status_code == 200
    # cand2 cannot see cand1's job
    assert client.get(f"/jobs/{job.id}", headers=h2).status_code == 403
