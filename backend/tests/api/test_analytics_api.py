from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import (
    DriveCandidate,
    Evaluation,
    Interview,
    InterviewStage,
    InterviewStatus,
    UserRole,
)

from .conftest import PASSWORD, iso, login, make_user


def test_analytics_overview(client, db, coordinator):
    h = coordinator
    r = client.get("/analytics/overview", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert "total_drives" in out
    assert "total_candidates_registered" in out
    assert "global_completion_rate" in out


def test_drive_analytics(client, db, published, coordinator):
    did = published["id"]
    h = coordinator

    r = client.get(f"/analytics/drives/{did}", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["drive_id"] == did
    assert out["total_enrolled"] == 3
    assert out["active_in_pipeline"] == 3
    assert len(out["stage_funnel"]) >= 1
    assert "room_utilization_percent" in out
    assert "rescue_operations_count" in out


def test_stages_analytics(client, db, published, coordinator):
    did = published["id"]
    h = coordinator

    r = client.get(f"/analytics/stages/{did}", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["drive_id"] == did
    assert len(out["stages"]) >= 1
    st = out["stages"][0]
    assert st["stage_name"] == "Tech"
    assert "conversion_rate" in st


def test_interviewers_analytics(client, db, published, coordinator):
    h = coordinator
    r = client.get("/analytics/interviewers", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["total_interviewers"] >= 2
    assert len(out["interviewers"]) >= 2
    ivr = out["interviewers"][0]
    assert "capacity_per_day" in ivr
    assert "utilization_rate" in ivr
    assert ivr["evaluator_calibration"] in ("calibrated", "harsh", "generous")


def test_analytics_forbidden_for_candidates(client, db):
    u = make_user(db, "cand_analytics@example.com", UserRole.CANDIDATE)
    h = login(client, "cand_analytics@example.com")
    assert client.get("/analytics/overview", headers=h).status_code == 403
