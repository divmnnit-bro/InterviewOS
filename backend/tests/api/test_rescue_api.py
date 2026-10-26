"""Stage 7: explanations and Ripple Rescue against a real database.

Same set-up as the other API tests (see conftest.py): 3 candidates, 2 interviewers, 1 room,
30-minute interviews on the first day. The drive is scheduled and published first.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, update

from app.models import (
    AuditEvent,
    Interview,
    InterviewStatus,
    Interviewer,
    Notification,
    PanelAssignment,
    RecruitmentDrive,
    Room,
    User,
    UserRole,
)
from app.scheduler.rescue import Change, Disruption, DisruptionKind, Move, Placement, RescuePlan
from app.scheduler.types import SolveStatus
from app.services import rescue as service

from .conftest import iso, login, make_user


@pytest.fixture(autouse=True)
def before_the_interviews(monkeypatch):
    """Pin 'now' to well before the drive, so the tests do not depend on the real date."""
    monkeypatch.setattr(service, "_now", lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))



def snapshot(db):
    """Everything a repair may change, as plain values."""
    db.expire_all()
    interviews = sorted(
        (str(i.id), i.status.value, i.start_time, i.end_time, i.room_id, i.version)
        for i in db.scalars(select(Interview))
    )
    panels = sorted(
        (str(p.interview_id), str(p.interviewer_id), p.is_active, p.start_time)
        for p in db.scalars(select(PanelAssignment))
    )
    version = db.scalar(select(RecruitmentDrive.schedule_version))
    audits = db.scalar(select(AuditEvent.id).where(AuditEvent.action == "schedule.rescue"))
    return interviews, panels, version, audits


def body(*disruptions, **extra):
    return {"disruptions": [
        {"kind": k, "resource_id": rid, "start_time": s, "end_time": e} for k, rid, s, e in disruptions
    ], **extra}


def first_interviewer(db):
    first = db.scalars(select(Interview).order_by(Interview.start_time)).first()
    return str(db.scalars(
        select(PanelAssignment.interviewer_id).where(PanelAssignment.interview_id == first.id)
    ).one())


# ----------------------------------------------------------------- explain
def test_explain_names_the_reason_and_a_verified_fix(client, db, drive):
    h, did = drive["headers"], drive["id"]
    db.execute(update(Interviewer).values(capacity=1))   # 2 interviewers x 1 per day < 3 candidates
    db.commit()

    r = client.post(f"/drives/{did}/schedule/explain", headers=h, json={})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["scheduled"] == 2 and out["unscheduled_count"] == 1 and not out["complete"]
    (e,) = out["explanations"]
    assert "capacity_contention" in e["reason_codes"] and e["summary"]
    assert e["fixes"], "a verified fix should be offered"
    assert {f["kind"] for f in e["fixes"]} <= {
        "add_room", "add_interviewer", "raise_daily_capacity",
        "widen_candidate_availability", "widen_interviewer_availability"}
    assert all(f["extra_interviews"] >= 1 for f in e["fixes"])

    # Read-only: nothing was saved.
    assert db.scalars(select(Interview).where(Interview.stage.has(drive_id=did))).all() == []
    assert db.scalar(select(AuditEvent.id).where(AuditEvent.entity_id == did, AuditEvent.action.like("schedule.%"))) is None


def test_explain_with_everyone_scheduled_has_nothing_to_explain(client, drive):
    r = client.post(f"/drives/{drive['id']}/schedule/explain", headers=drive["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["explanations"] == [] and r.json()["unscheduled_count"] == 0 and r.json()["complete"]


# ----------------------------------------------------------------- preview
def test_preview_swaps_a_panel_member_without_touching_candidates(client, db, published):
    h, did = published["headers"], published["id"]
    out_iv = first_interviewer(db)
    before = snapshot(db)

    r = client.post(f"/drives/{did}/rescue/preview", headers=h,
                    json=body(("interviewer_out", out_iv, iso(9), iso(17))))
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["schedule_version"] == 1 and plan["fully_repaired"] and plan["plan_fingerprint"]
    assert plan["moves"] and all(m["changes"] == ["panel"] for m in plan["moves"])
    assert all(m["directly_affected"] for m in plan["moves"])
    assert plan["candidates_to_notify"] == [] and out_iv in plan["interviewers_to_notify"]
    assert plan["dropped"] == [] and plan["needs_manual"] == []

    assert snapshot(db) == before   # a preview writes nothing


# ------------------------------------------------------------------- apply
def test_apply_panel_swap_is_atomic_audited_and_notified(client, db, published):
    h, did = published["headers"], published["id"]
    out_iv = first_interviewer(db)
    req = body(("interviewer_out", out_iv, iso(9), iso(17)))
    plan = client.post(f"/drives/{did}/rescue/preview", headers=h, json=req).json()
    times_before = {str(i.id): (i.start_time, i.room_id) for i in db.scalars(select(Interview))}

    r = client.post(f"/drives/{did}/rescue/apply", headers=h, json={
        **req, "expected_version": plan["schedule_version"], "plan_fingerprint": plan["plan_fingerprint"]})
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["applied"] and done["new_schedule_version"] == 2
    assert done["moved_count"] == len(plan["moves"]) and done["cancelled_count"] == 0
    assert done["notifications_created"] > 0

    db.expire_all()
    # The absent interviewer sits on nothing; everyone still has an interview at the same time and room.
    active = db.scalars(select(PanelAssignment).where(PanelAssignment.is_active.is_(True))).all()
    assert len(active) == 3 and all(str(p.interviewer_id) != out_iv for p in active)
    for i in db.scalars(select(Interview)):
        assert i.status == InterviewStatus.SCHEDULED
        assert (i.start_time, i.room_id) == times_before[str(i.id)]
    assert db.scalar(select(RecruitmentDrive.schedule_version).where(RecruitmentDrive.id == did)) == 2

    audit = db.scalars(select(AuditEvent).where(AuditEvent.entity_id == did, AuditEvent.action == "schedule.rescue")).one()
    assert audit.details["from_version"] == 1 and audit.details["to_version"] == 2
    assert len(audit.details["moved"]) == len(plan["moves"])
    kinds = {n.type for n in db.scalars(select(Notification))}
    assert kinds == {"interview_panel_changed"}   # only interviewers hear about a panel swap


def test_apply_after_a_room_closure_moves_candidates_and_tells_them(client, db, published):
    h, did = published["headers"], published["id"]
    room = published["room"]
    req = body(("room_out", room, iso(9), iso(9, 30)))     # the 09:00 interview loses its room
    plan = client.post(f"/drives/{did}/rescue/preview", headers=h, json=req).json()
    assert plan["fully_repaired"] and len(plan["affected"]) == 1
    assert any("time" in m["changes"] and m["directly_affected"] for m in plan["moves"])

    r = client.post(f"/drives/{did}/rescue/apply", headers=h, json={**req, "expected_version": 1})
    assert r.status_code == 200, r.text

    db.expire_all()
    rows = db.scalars(select(Interview).order_by(Interview.start_time)).all()
    assert len(rows) == 3 and {i.status for i in rows} == {InterviewStatus.SCHEDULED}
    # Nobody is in the closed room during the closure, and the room was never double booked.
    for i in rows:
        assert not (i.start_time < datetime.fromisoformat(iso(9, 30)) and i.end_time > datetime.fromisoformat(iso(9)))
    assert len({i.start_time for i in rows}) == 3
    moved_candidates = {c for m in plan["moves"] if m["notifies_candidate"] for c in [m["candidate_id"]]}
    told = {str(n.user_id) for n in db.scalars(select(Notification).where(Notification.type == "interview_rescheduled"))}
    assert moved_candidates <= told


def test_candidates_who_cannot_be_re_placed_are_cancelled_and_told(client, db, published):
    h, did = published["headers"], published["id"]
    # The only room is out for the whole of the one day everybody is available.
    req = body(("room_out", published["room"], iso(0), iso(0, day=1)))
    plan = client.post(f"/drives/{did}/rescue/preview", headers=h, json=req).json()
    assert not plan["fully_repaired"] and len(plan["dropped"]) == 3 and plan["moves"] == []
    assert all(d["reasons"] for d in plan["dropped"])

    r = client.post(f"/drives/{did}/rescue/apply", headers=h, json={**req, "expected_version": 1})
    assert r.status_code == 200, r.text
    assert r.json()["cancelled_count"] == 3

    db.expire_all()
    assert {i.status for i in db.scalars(select(Interview))} == {InterviewStatus.CANCELLED}
    assert db.scalars(select(PanelAssignment).where(PanelAssignment.is_active.is_(True))).all() == []
    cancelled = db.scalars(select(Notification).where(Notification.type == "interview_cancelled")).all()
    assert {str(n.user_id) for n in cancelled} >= set(published["candidates"])


def test_a_deactivated_room_counts_as_a_disruption(client, db, published):
    h, did = published["headers"], published["id"]
    db.get(Room, uuid.UUID(published["room"])).is_active = False
    db.commit()
    # The reported disruption is unrelated; the closed room is found by itself.
    c0 = published["candidates"][0]
    plan = client.post(f"/drives/{did}/rescue/preview", headers=h,
                       json=body(("candidate_out", c0, iso(15), iso(16)))).json()
    implicit = [d for d in plan["disruptions"] if d["implicit"]]
    assert [(d["kind"], d["resource_id"]) for d in implicit] == [("room_out", published["room"])]
    assert len(plan["affected"]) == 3 and len(plan["dropped"]) == 3   # no other room exists


def test_started_interviews_are_never_moved(client, db, monkeypatch, published):
    h, did = published["headers"], published["id"]
    monkeypatch.setattr(service, "_now", lambda: datetime.fromisoformat(iso(9, 15)))   # 09:00 has started
    first = db.scalars(select(Interview).order_by(Interview.start_time)).first()
    out_iv = first_interviewer(db)
    plan = client.post(f"/drives/{did}/rescue/preview", headers=h,
                       json=body(("interviewer_out", out_iv, iso(9), iso(9, 30)))).json()
    assert plan["needs_manual"] == [str(first.id)]
    assert all(m["interview_id"] != str(first.id) for m in plan["moves"])
    assert str(first.id) not in {d["interview_id"] for d in plan["dropped"]}


def test_nothing_hit_means_nothing_written(client, db, published):
    h, did = published["headers"], published["id"]
    before = snapshot(db)
    r = client.post(f"/drives/{did}/rescue/apply", headers=h, json={
        **body(("room_out", published["room"], iso(15), iso(16))), "expected_version": 1})
    assert r.status_code == 200, r.text
    assert r.json()["applied"] is False and r.json()["new_schedule_version"] == 1
    assert snapshot(db) == before


# ---------------------------------------------------- conflicts and safety
def test_apply_with_an_old_version_is_refused_and_changes_nothing(client, db, published):
    h, did = published["headers"], published["id"]
    before = snapshot(db)
    r = client.post(f"/drives/{did}/rescue/apply", headers=h, json={
        **body(("interviewer_out", first_interviewer(db), iso(9), iso(17))), "expected_version": 0})
    assert r.status_code == 409 and r.json()["error"] == "stale_schedule_version"
    assert snapshot(db) == before


def test_apply_with_a_different_plan_than_previewed_is_refused(client, db, published):
    h, did = published["headers"], published["id"]
    before = snapshot(db)
    r = client.post(f"/drives/{did}/rescue/apply", headers=h, json={
        **body(("interviewer_out", first_interviewer(db), iso(9), iso(17))),
        "expected_version": 1, "plan_fingerprint": "0" * 32})
    assert r.status_code == 409 and r.json()["error"] == "plan_changed"
    assert snapshot(db) == before


def test_applying_the_same_repair_twice_is_stale_the_second_time(client, db, published):
    h, did = published["headers"], published["id"]
    req = {**body(("interviewer_out", first_interviewer(db), iso(9), iso(17))), "expected_version": 1}
    assert client.post(f"/drives/{did}/rescue/apply", headers=h, json=req).status_code == 200
    again = client.post(f"/drives/{did}/rescue/apply", headers=h, json=req)
    assert again.status_code == 409 and again.json()["error"] == "stale_schedule_version"


def test_a_failure_part_way_through_rolls_everything_back(db, published, monkeypatch):
    coordinator = db.scalars(select(User).where(User.role == UserRole.COORDINATOR)).first()
    real = service._write_plan

    def write_then_crash(session, plan):
        real(session, plan)
        raise RuntimeError("boom after the writes")

    monkeypatch.setattr(service, "_write_plan", write_then_crash)
    before = snapshot(db)
    from app.schemas.schedule import ProposeOptions
    with pytest.raises(RuntimeError):
        service.apply_rescue(
            db, uuid.UUID(published["id"]), coordinator.id,
            [Disruption(DisruptionKind.INTERVIEWER_OUT, uuid.UUID(first_interviewer(db)),
                        datetime.fromisoformat(iso(9)), datetime.fromisoformat(iso(17)))],
            ProposeOptions(), expected_version=1)
    assert snapshot(db) == before


def test_moves_that_swap_slots_do_not_trip_the_exclusion_constraints(db, published):
    """A takes B's slot and B takes A's: legal as a whole, illegal one statement at a time."""
    a, b = db.scalars(select(Interview).order_by(Interview.start_time).limit(2)).all()
    pa = {p.interview_id: p.interviewer_id for p in db.scalars(select(PanelAssignment))}
    place = lambda i: Placement(i.start_time, i.end_time, i.room_id, (pa[i.id],))   # noqa: E731

    def move(x, y):
        return Move(x.id, x.candidate_id, x.stage_id, place(x), place(y),
                    frozenset({Change.TIME}), True)

    plan = RescuePlan(
        status=SolveStatus.OPTIMAL, moves=(move(a, b), move(b, a)), dropped=(), needs_manual=(),
        unchanged=(), affected=(a.id, b.id), candidates_to_notify=(), interviewers_to_notify=(),
        new_schedule=(), violations=())
    old_a, old_b = a.start_time, b.start_time
    service._write_plan(db, plan)
    db.flush()
    db.expire_all()
    assert (db.get(Interview, a.id).start_time, db.get(Interview, b.id).start_time) == (old_b, old_a)
    # The panel rows followed their interviews.
    assert {p.start_time for p in db.scalars(select(PanelAssignment).where(PanelAssignment.interview_id == a.id))} == {old_b}


def test_unknown_resources_and_empty_drives_are_rejected(client, db, drive):
    h, did = drive["headers"], drive["id"]
    # Nothing published yet.
    r = client.post(f"/drives/{did}/rescue/preview", headers=h,
                    json=body(("room_out", drive["room"], iso(9), iso(10))))
    assert r.status_code == 409
    client.post(f"/drives/{did}/schedule/propose", headers=h)
    client.post(f"/drives/{did}/schedule/publish", headers=h, json={"expected_version": 0})
    r = client.post(f"/drives/{did}/rescue/preview", headers=h,
                    json=body(("room_out", str(uuid.uuid4()), iso(9), iso(10))))
    assert r.status_code == 422
    assert client.post(f"/drives/{did}/rescue/preview", headers=h, json={"disruptions": []}).status_code == 422
    bad = body(("room_out", drive["room"], iso(10), iso(9)))
    assert client.post(f"/drives/{did}/rescue/preview", headers=h, json=bad).status_code == 422


# -------------------------------------------------------------- permissions
def test_only_coordinators_can_explain_or_rescue(client, db, published):
    did = published["id"]
    make_user(db, "cand@example.com", UserRole.CANDIDATE)
    candidate = login(client, "cand@example.com")
    interviewer = login(client, "iv0@example.com")
    req = body(("room_out", published["room"], iso(9), iso(10)))
    calls = [
        (f"/drives/{did}/schedule/explain", {}),
        (f"/drives/{did}/rescue/preview", req),
        (f"/drives/{did}/rescue/apply", {**req, "expected_version": 1}),
    ]
    for url, payload in calls:
        assert client.post(url, headers=candidate, json=payload).status_code == 403, url
        assert client.post(url, headers=interviewer, json=payload).status_code == 403, url
        assert client.post(url, json=payload).status_code == 401, url
    assert db.scalar(select(AuditEvent.id).where(AuditEvent.action == "schedule.rescue")) is None
