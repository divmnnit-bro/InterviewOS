import uuid

import pytest
from sqlalchemy import select

from app.models import Interview, InterviewStatus, RecruitmentDrive
from app.scheduler import ScheduleResult, SolveStatus
from app.services import scheduling
from app.services.errors import StaleScheduleVersion

from .conftest import iso


def test_propose_then_publish(client, db, drive):
    h, did = drive["headers"], drive["id"]
    r = client.post(f"/drives/{did}/schedule/propose", headers=h)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["complete"] and len(p["interviews"]) == 3 and p["schedule_version"] == 0
    assert {i["status"] for i in p["interviews"]} == {"proposed"}
    assert all(len(i["interviewer_ids"]) == 1 for i in p["interviews"])

    pub = client.post(f"/drives/{did}/schedule/publish", headers=h, json={"expected_version": 0})
    assert pub.status_code == 200, pub.text
    assert pub.json() == {"drive_id": did, "schedule_version": 1, "published_interviews": 3, "superseded_dropped": 0}

    rows = db.scalars(select(Interview)).all()
    assert {i.status for i in rows} == {InterviewStatus.SCHEDULED}
    drv = db.get(RecruitmentDrive, uuid.UUID(did))
    db.refresh(drv)
    assert drv.schedule_version == 1 and drv.status.value == "published"

    # The same publish again is a stale request.
    again = client.post(f"/drives/{did}/schedule/publish", headers=h, json={"expected_version": 0})
    assert again.status_code == 409


def test_published_candidates_are_not_scheduled_twice(client, drive):
    h, did = drive["headers"], drive["id"]
    client.post(f"/drives/{did}/schedule/propose", headers=h)
    client.post(f"/drives/{did}/schedule/publish", headers=h, json={"expected_version": 0})
    p = client.post(f"/drives/{did}/schedule/propose", headers=h).json()
    assert p["interviews"] == [] and p["schedule_version"] == 1


def test_new_proposal_replaces_the_old_one(client, drive):
    h, did = drive["headers"], drive["id"]
    client.post(f"/drives/{did}/schedule/propose", headers=h)
    client.post(f"/drives/{did}/schedule/propose", headers=h)
    cur = client.get(f"/drives/{did}/schedule/proposal", headers=h).json()
    assert len(cur["interviews"]) == 3  # not 6


def test_publish_with_no_proposal_is_409(client, drive):
    r = client.post(f"/drives/{drive['id']}/schedule/publish", headers=drive["headers"],
                    json={"expected_version": 0})
    assert r.status_code == 409


def test_proposal_built_on_an_old_version_is_rejected(db, drive):
    did = uuid.UUID(drive["id"])
    drv = db.get(RecruitmentDrive, did)
    drv.schedule_version = 5          # someone published in the meantime
    db.commit()
    with pytest.raises(StaleScheduleVersion):
        scheduling._save_proposal(db, did, drv.created_by, expected_version=4,
                                  result=ScheduleResult(
                                      status=SolveStatus.NOTHING_TO_SCHEDULE,
                                      interviews=(), unscheduled=()))


def test_a_proposal_that_fails_verification_is_never_saved(client, db, drive, monkeypatch):
    monkeypatch.setattr(scheduling, "verify", lambda inp, res: ["room double-booked (fake)"])
    r = client.post(f"/drives/{drive['id']}/schedule/propose", headers=drive["headers"])
    assert r.status_code == 422
    assert db.scalars(select(Interview)).all() == []


def test_room_availability_windows_reach_the_solver(client, drive):
    h, did = drive["headers"], drive["id"]
    # Room open only 09:00-09:30: exactly one 30-minute interview fits with a single room.
    r = client.put(f"/rooms/{drive['room']}/availability", headers=h,
                   json={"windows": [{"start_time": iso(9), "end_time": iso(9, 30)}]})
    assert r.status_code == 200
    p = client.post(f"/drives/{did}/schedule/propose", headers=h).json()
    assert len(p["interviews"]) == 1 and len(p["unscheduled"]) == 2
    # Clearing the windows opens the room for the whole drive again.
    client.put(f"/rooms/{drive['room']}/availability", headers=h, json={"windows": []})
    p = client.post(f"/drives/{did}/schedule/propose", headers=h).json()
    assert len(p["interviews"]) == 3


def test_stages_are_locked_after_publish(client, drive):
    h, did = drive["headers"], drive["id"]
    client.post(f"/drives/{did}/schedule/propose", headers=h)
    client.post(f"/drives/{did}/schedule/publish", headers=h, json={"expected_version": 0})
    r = client.post(f"/drives/{did}/stages", headers=h, json={
        "order_index": 2, "name": "HR", "stage_type": "hr", "duration_minutes": 20})
    assert r.status_code == 409
