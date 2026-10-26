"""Stage 8: evaluations and the candidate pipeline, against a real database.

Same set-up as the other API tests (see conftest.py): 3 candidates, 2 interviewers, 1 room.
Here the drive has two rounds, Tech (order 1) and HR (order 2). Only Tech is scheduled, and
published, so each candidate has one Tech interview on the first day with a one-person panel.
"Now" is pinned to after those interviews, so they count as held.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.models import (
    AuditEvent,
    DriveCandidate,
    DriveCandidateStatus,
    Evaluation,
    Interview,
    InterviewStatus,
    PanelAssignment,
    Recommendation,
    User,
    UserRole,
)
from app.schemas.evaluation import EvaluationCreate
from app.schemas.pipeline import CandidateStageDecision
from app.services import evaluations as evaluations_service
from app.services import pipeline as pipeline_service

from .conftest import PASSWORD, T0, login

NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)      # after every Tech interview, before day 3


@pytest.fixture(autouse=True)
def after_the_interviews(monkeypatch):
    monkeypatch.setattr(evaluations_service, "_now", lambda: NOW)
    monkeypatch.setattr(pipeline_service, "_now", lambda: NOW)


@pytest.fixture()
def rounds(client, drive):
    """The standard drive plus an HR round, with the Tech round scheduled and published."""
    h, did = drive["headers"], drive["id"]
    r = client.post(f"/drives/{did}/stages", headers=h, json={
        "order_index": 2, "name": "HR", "stage_type": "hr", "duration_minutes": 30, "panel_size": 1})
    assert r.status_code == 201, r.text
    assert client.post(f"/drives/{did}/schedule/propose", headers=h).status_code == 200
    assert client.post(f"/drives/{did}/schedule/publish", headers=h, json={"expected_version": 0}).status_code == 200
    stages = client.get(f"/drives/{did}/stages", headers=h).json()
    return {**drive, "tech": stages[0]["id"], "hr": stages[1]["id"]}


# ---------------------------------------------------------------- helpers
def ev(rubric=None, score=None, rec="hire", feedback="Clear thinking, good tests.", **extra):
    body = {"recommendation": rec, "feedback": feedback, **extra}
    body["rubric"] = rubric if rubric is not None else ({} if score is not None else
                                                       {"communication": 8, "problem_solving": 8})
    if score is not None:
        body["score"] = score
    return body


def interview_of(db, candidate_id) -> Interview:
    return db.scalars(select(Interview).where(Interview.candidate_id == uuid.UUID(candidate_id))
                      .order_by(Interview.start_time)).first()


def panelist(client, db, iv):
    """(user, auth headers) of the single active panel member of `iv`."""
    pa = db.scalars(select(PanelAssignment).where(
        PanelAssignment.interview_id == iv.id, PanelAssignment.is_active.is_(True))).one()
    user = db.get(User, pa.interviewer_id)
    return user, login(client, user.email)


def evaluate(client, db, candidate_id, score=8, rec="hire"):
    iv = interview_of(db, candidate_id)
    _, h = panelist(client, db, iv)
    r = client.post(f"/interviews/{iv.id}/evaluations", headers=h, json=ev(score=score, rec=rec))
    assert r.status_code in (200, 201), r.text
    return iv


def decide(client, rounds, path, candidate_id, stage_id, **extra):
    return client.post(f"/drives/{rounds['id']}/candidates/{candidate_id}/{path}", headers=rounds["headers"],
                       json={"stage_id": stage_id, **extra})


def add_interview(db, candidate_id, stage_id, interviewers, *, day=0, hour=12,
                  status=InterviewStatus.CONFIRMED) -> Interview:
    """An interview inserted directly (any panel size, any time). No room, so no room clashes."""
    start = T0 + timedelta(days=day, hours=hour)
    iv = Interview(candidate_id=uuid.UUID(candidate_id), stage_id=uuid.UUID(stage_id), room_id=None,
                   start_time=start, end_time=start + timedelta(minutes=30), status=status)
    iv.panel = [PanelAssignment(interviewer_id=u.id, start_time=start, end_time=start + timedelta(minutes=30))
                for u in interviewers]
    db.add(iv)
    db.commit()
    return iv


def interviewer_users(db) -> list[User]:
    return [db.scalars(select(User).where(User.email == f"iv{n}@example.com")).one() for n in range(2)]


# ------------------------------------------------- schema rules (no database)
def test_schema_derives_score_and_rejects_bad_input():
    assert EvaluationCreate(rubric={"a": 8, "b": 6}, recommendation="hire").overall_score() == 7.0
    assert EvaluationCreate(rubric={"a": 8}, score=5, recommendation="hire").overall_score() == 5.0
    assert EvaluationCreate(score=4.5, recommendation="no_hire").rubric == {}
    assert EvaluationCreate(score=4, feedback="   ", recommendation="hire").feedback is None
    for bad in (
        dict(recommendation="hire"),                                    # no rating at all
        dict(rubric={"a": 11}, recommendation="hire"),                  # out of range
        dict(rubric={"a": float("nan")}, recommendation="hire"),
        dict(rubric={"Skill": 5, "skill": 6}, recommendation="hire"),   # duplicate criterion
        dict(rubric={" ": 5}, recommendation="hire"),
        dict(score=3, recommendation="maybe"),                          # not a recommendation
        dict(score=3),                                                  # recommendation required
        dict(rubric={f"c{i}": 5 for i in range(21)}, recommendation="hire"),
    ):
        with pytest.raises(ValidationError):
            EvaluationCreate(**bad)


def test_decision_override_needs_a_real_reason():
    sid = uuid.uuid4()
    assert CandidateStageDecision(stage_id=sid).override is False
    with pytest.raises(ValidationError):
        CandidateStageDecision(stage_id=sid, override=True)
    with pytest.raises(ValidationError):
        CandidateStageDecision(stage_id=sid, override=True, override_reason="too short")
    assert CandidateStageDecision(stage_id=sid, override=True, override_reason="Strong referral from the panel").override


# ------------------------------------------------------- submitting feedback
def test_panelist_submits_then_revises_their_feedback(client, db, rounds):
    c0 = rounds["candidates"][0]
    iv = interview_of(db, c0)
    user, h = panelist(client, db, iv)

    r = client.post(f"/interviews/{iv.id}/evaluations", headers=h,
                    json=ev(rubric={"communication": 8, "problem_solving": 6}))
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["score"] == 7.0 and out["recommendation"] == "hire"
    assert out["interviewer_id"] == str(user.id) and out["interview_id"] == str(iv.id) and out["submitted_at"]

    db.expire_all()
    row = db.scalars(select(Evaluation)).one()
    assert float(row.score) == 7.0 and row.rubric == {"communication": 8.0, "problem_solving": 6.0}
    assert row.recommendation == Recommendation.HIRE and row.interviewer_id == user.id
    assert db.get(Interview, iv.id).status == InterviewStatus.COMPLETED     # the whole panel has reported
    audit = db.scalars(select(AuditEvent).where(AuditEvent.action == "evaluation.submit")).one()
    assert audit.actor_id == user.id and audit.details["interview_completed"] is True
    assert "feedback" not in audit.details                                  # the text stays out of the audit log

    again = client.post(f"/interviews/{iv.id}/evaluations", headers=h, json=ev(score=9, rec="strong_hire"))
    assert again.status_code == 200 and again.json()["id"] == out["id"] and again.json()["score"] == 9.0
    db.expire_all()
    assert len(db.scalars(select(Evaluation)).all()) == 1
    assert db.scalars(select(AuditEvent).where(AuditEvent.action == "evaluation.update")).one()


def test_my_interviews_reports_only_the_signed_in_panelists_evaluation(client, db, rounds):
    candidate_id = rounds["candidates"][0]
    interview = interview_of(db, candidate_id)
    _, interviewer_headers = panelist(client, db, interview)

    before = client.get("/me/interviews", headers=interviewer_headers)
    assert before.status_code == 200
    assert next(item for item in before.json() if item["id"] == str(interview.id))["evaluation_submitted"] is False

    result = client.post(f"/interviews/{interview.id}/evaluations", headers=interviewer_headers, json=ev(score=8))
    assert result.status_code == 201, result.text
    after = client.get("/me/interviews", headers=interviewer_headers)
    assert next(item for item in after.json() if item["id"] == str(interview.id))["evaluation_submitted"] is True

    candidate_headers = login(client, "c0@example.com")
    candidate_view = client.get("/me/interviews", headers=candidate_headers)
    assert next(item for item in candidate_view.json() if item["id"] == str(interview.id))["evaluation_submitted"] is None


def test_only_the_assigned_panel_may_submit(client, db, rounds):
    h = rounds["headers"]
    iv = interview_of(db, rounds["candidates"][0])
    on_panel, _ = panelist(client, db, iv)
    outsider = next(u for u in interviewer_users(db) if u.id != on_panel.id)
    outsider_h = login(client, outsider.email)

    assert client.post(f"/interviews/{iv.id}/evaluations", headers=outsider_h, json=ev()).status_code == 404
    cand_h = login(client, "c0@example.com")
    assert client.post(f"/interviews/{iv.id}/evaluations", headers=cand_h, json=ev()).status_code == 403
    assert client.post(f"/interviews/{iv.id}/evaluations", json=ev()).status_code == 401
    # an interviewer cannot write feedback in a colleague's name
    r = client.post(f"/interviews/{iv.id}/evaluations", headers=outsider_h, json=ev(on_behalf_of=str(on_panel.id)))
    assert r.status_code == 403
    assert client.post(f"/interviews/{uuid.uuid4()}/evaluations", headers=h, json=ev()).status_code == 404
    db.expire_all()
    assert db.scalars(select(Evaluation)).all() == []


def test_coordinator_records_feedback_for_a_named_panelist(client, db, rounds):
    h = rounds["headers"]
    iv = interview_of(db, rounds["candidates"][0])
    on_panel, _ = panelist(client, db, iv)
    outsider = next(u for u in interviewer_users(db) if u.id != on_panel.id)

    assert client.post(f"/interviews/{iv.id}/evaluations", headers=h, json=ev()).status_code == 422
    r = client.post(f"/interviews/{iv.id}/evaluations", headers=h, json=ev(on_behalf_of=str(outsider.id)))
    assert r.status_code == 422                                              # not on this panel
    r = client.post(f"/interviews/{iv.id}/evaluations", headers=h, json=ev(on_behalf_of=str(on_panel.id)))
    assert r.status_code == 201 and r.json()["interviewer_id"] == str(on_panel.id)
    db.expire_all()
    audit = db.scalars(select(AuditEvent).where(AuditEvent.action == "evaluation.submit")).one()
    assert audit.details["on_behalf_of"] is True


def test_interview_must_have_started_and_still_be_on(client, db, rounds, monkeypatch):
    iv = interview_of(db, rounds["candidates"][0])
    _, h = panelist(client, db, iv)

    # The solver decides which slot each candidate gets, so take the times from the interview itself.
    monkeypatch.setattr(evaluations_service, "_now", lambda: iv.start_time - timedelta(minutes=1))
    assert client.post(f"/interviews/{iv.id}/evaluations", headers=h, json=ev()).status_code == 409

    monkeypatch.setattr(evaluations_service, "_now", lambda: iv.start_time + timedelta(minutes=10))  # mid-interview
    assert client.post(f"/interviews/{iv.id}/evaluations", headers=h, json=ev()).status_code == 201
    db.expire_all()
    assert db.get(Interview, iv.id).status != InterviewStatus.COMPLETED     # not over yet, so not completed

    db.get(Interview, iv.id).status = InterviewStatus.CANCELLED
    db.commit()
    assert client.post(f"/interviews/{iv.id}/evaluations", headers=h, json=ev()).status_code == 409


# ------------------------------------------------------ reading feedback
def test_panelists_see_colleagues_only_after_submitting(client, db, rounds):
    h, c0 = rounds["headers"], rounds["candidates"][0]
    a, b = interviewer_users(db)
    ha, hb = login(client, a.email), login(client, b.email)
    iv = add_interview(db, c0, rounds["tech"], [a, b])
    outsider = client.post("/users", headers=h, json={
        "name": "out", "email": "out@example.com", "password": PASSWORD, "role": "interviewer"}).json()
    ho = login(client, "out@example.com")
    url = f"/interviews/{iv.id}/evaluations"

    assert client.post(url, headers=hb, json=ev(score=6, rec="no_hire")).status_code == 201
    mine = client.get(url, headers=ha).json()                    # a has not submitted yet
    assert mine["visibility"] == "own_only" and mine["evaluations"] == []
    assert mine["panel_size"] == 2 and mine["submitted_count"] == 1

    assert client.post(url, headers=ha, json=ev(score=9, rec="strong_hire")).status_code == 201
    seen = client.get(url, headers=ha).json()
    assert seen["visibility"] == "all" and {e["score"] for e in seen["evaluations"]} == {6.0, 9.0}

    coord = client.get(url, headers=h).json()
    assert coord["visibility"] == "all" and len(coord["evaluations"]) == 2
    assert client.get(url, headers=ho).status_code == 404        # not on the panel
    assert client.get(url, headers=login(client, "c0@example.com")).status_code == 403
    assert client.get(f"/interviews/{uuid.uuid4()}/evaluations", headers=h).status_code == 404
    assert outsider["role"] == "interviewer"


# ------------------------------------------------------------- decisions
def test_advance_to_the_next_round_then_to_selected(client, db, rounds):
    c0 = rounds["candidates"][0]
    evaluate(client, db, c0, score=8)

    r = decide(client, rounds, "advance", c0, rounds["tech"], notes="Strong round")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["outcome"] == "advanced" and out["status"] == "active" and out["current_stage_id"] == rounds["hr"]
    assert out["average_score"] == 8.0 and out["rule_met"] is True and out["override_used"] is False
    db.expire_all()
    row = db.get(DriveCandidate, (uuid.UUID(rounds["id"]), uuid.UUID(c0)))
    assert str(row.current_stage_id) == rounds["hr"] and row.status == DriveCandidateStatus.ACTIVE

    # the same click again is stale: the candidate is no longer in the Tech round
    again = decide(client, rounds, "advance", c0, rounds["tech"])
    assert again.status_code == 409 and again.json()["details"]["current_stage_id"] == rounds["hr"]

    # HR has had no interview, so passing needs an explicit, explained override
    blocked = decide(client, rounds, "advance", c0, rounds["hr"])
    assert blocked.status_code == 409 and blocked.json()["error"] == "decision_blocked"
    assert [b["code"] for b in blocked.json()["details"]] == ["no_interview"]
    assert decide(client, rounds, "advance", c0, rounds["hr"], override=True).status_code == 422
    done = decide(client, rounds, "advance", c0, rounds["hr"], override=True,
                  override_reason="Interviewed off-system by the hiring manager")
    assert done.status_code == 200 and done.json()["outcome"] == "selected"
    assert done.json()["status"] == "selected" and done.json()["override_used"] is True
    assert decide(client, rounds, "advance", c0, rounds["hr"]).status_code == 409   # already selected

    db.expire_all()
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "pipeline.advance")
                        .order_by(AuditEvent.timestamp, AuditEvent.id)).all()
    assert len(events) == 2
    last = max(events, key=lambda e: e.details["outcome"] == "selected")
    assert last.details["overridden"] == ["no_interview"] and last.details["override_reason"]


def test_a_pass_needs_complete_feedback_and_a_met_rule_unless_overridden(client, db, rounds):
    c1, c2 = rounds["candidates"][1], rounds["candidates"][2]

    # no feedback yet from the one panel member
    r = decide(client, rounds, "advance", c2, rounds["tech"])
    assert r.status_code == 409 and [b["code"] for b in r.json()["details"]] == ["evaluations_incomplete"]

    # average 3.0 is below the default minimum of 6.0
    evaluate(client, db, c1, score=3, rec="no_hire")
    r = decide(client, rounds, "advance", c1, rounds["tech"])
    assert r.status_code == 409 and [b["code"] for b in r.json()["details"]] == ["rule_not_met"]

    r = decide(client, rounds, "advance", c1, rounds["tech"], override=True,
               override_reason="Panel agreed the score was affected by a network outage")
    assert r.status_code == 200 and r.json()["override_used"] is True and r.json()["rule_met"] is False
    db.expire_all()
    audit = db.scalars(select(AuditEvent).where(AuditEvent.action == "pipeline.advance")).one()
    assert audit.details["overridden"] == ["rule_not_met"] and audit.details["average_score"] == 3.0


def test_reject_cancels_future_interviews_and_locks_feedback(client, db, rounds):
    c2 = rounds["candidates"][2]
    a, _ = interviewer_users(db)
    future = add_interview(db, c2, rounds["hr"], [a], day=4)               # after "now", so not yet held
    tech = interview_of(db, c2)
    _, tech_h = panelist(client, db, tech)

    r = decide(client, rounds, "reject", c2, rounds["tech"], notes="Did not meet the bar")
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "rejected" and r.json()["status"] == "rejected"
    assert r.json()["cancelled_interviews"] == 1

    db.expire_all()
    assert db.get(Interview, future.id).status == InterviewStatus.CANCELLED
    assert not db.scalars(select(PanelAssignment).where(PanelAssignment.interview_id == future.id)).one().is_active
    assert db.get(Interview, tech.id).status != InterviewStatus.CANCELLED     # already held: kept
    audit = db.scalars(select(AuditEvent).where(AuditEvent.action == "pipeline.reject")).one()
    assert audit.details["cancelled_interview_ids"] == [str(future.id)]

    assert decide(client, rounds, "reject", c2, rounds["tech"]).status_code == 409
    assert decide(client, rounds, "advance", c2, rounds["tech"]).status_code == 409
    late = client.post(f"/interviews/{tech.id}/evaluations", headers=tech_h, json=ev())
    assert late.status_code == 409 and late.json()["error"] == "evaluation_locked"


def test_decisions_are_coordinator_only_and_validate_their_targets(client, db, rounds):
    c0 = rounds["candidates"][0]
    path = f"/drives/{rounds['id']}/candidates/{c0}"
    body = {"stage_id": rounds["tech"]}
    iv_h = login(client, "iv0@example.com")
    cand_h = login(client, "c0@example.com")
    for suffix in ("advance", "reject"):
        assert client.post(f"{path}/{suffix}", json=body).status_code == 401
        assert client.post(f"{path}/{suffix}", headers=iv_h, json=body).status_code == 403
        assert client.post(f"{path}/{suffix}", headers=cand_h, json=body).status_code == 403
    assert client.get(f"/drives/{rounds['id']}/pipeline").status_code == 401
    assert client.get(f"/drives/{rounds['id']}/pipeline", headers=iv_h).status_code == 403
    assert client.get(f"/drives/{rounds['id']}/pipeline", headers=cand_h).status_code == 403

    h = rounds["headers"]
    assert client.post(f"/drives/{uuid.uuid4()}/candidates/{c0}/reject", headers=h, json=body).status_code == 404
    assert client.post(f"/drives/{rounds['id']}/candidates/{uuid.uuid4()}/reject", headers=h, json=body).status_code == 404
    wrong_round = client.post(f"{path}/reject", headers=h, json={"stage_id": rounds["hr"]})
    assert wrong_round.status_code == 409
    db.expire_all()
    assert db.get(DriveCandidate, (uuid.UUID(rounds["id"]), uuid.UUID(c0))).status == DriveCandidateStatus.ACTIVE


# --------------------------------------------------------------- pipeline
def test_pipeline_overview_across_two_rounds(client, db, rounds):
    h, did = rounds["headers"], rounds["id"]
    c0, c1, c2 = rounds["candidates"]
    evaluate(client, db, c0, score=8)
    evaluate(client, db, c1, score=3, rec="no_hire")
    evaluate(client, db, c2, score=7)
    assert decide(client, rounds, "advance", c0, rounds["tech"]).status_code == 200
    assert decide(client, rounds, "reject", c1, rounds["tech"]).status_code == 200

    r = client.get(f"/drives/{did}/pipeline", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status_counts"] == {"active": 2, "rejected": 1, "selected": 0, "withdrawn": 0}

    tech, hr = out["stages"]
    assert (tech["name"], tech["passed"], tech["rejected"], tech["awaiting_decision"], tech["candidates_here"]) \
        == ("Tech", 1, 1, 1, 1)
    assert (hr["name"], hr["passed"], hr["rejected"], hr["awaiting_decision"], hr["candidates_here"]) \
        == ("HR", 0, 0, 0, 1)

    by_id = {c["candidate_id"]: c for c in out["candidates"]}
    states = lambda cid: [s["state"] for s in by_id[cid]["stages"]]
    assert states(c0) == ["passed", "pending"] and by_id[c0]["current_stage_id"] == rounds["hr"]
    assert states(c1) == ["rejected", "not_reached"] and by_id[c1]["status"] == "rejected"
    assert states(c2) == ["awaiting_decision", "not_reached"]
    tech_c0 = by_id[c0]["stages"][0]
    assert tech_c0["evaluations"] == 1 and tech_c0["average_score"] == 8.0 and tech_c0["rule_met"] is True
    assert tech_c0["interview_id"] and tech_c0["interview_status"] == "completed"
    assert by_id[c1]["stages"][0]["rule_met"] is False

    only_rejected = client.get(f"/drives/{did}/pipeline?status=rejected", headers=h).json()
    assert [c["candidate_id"] for c in only_rejected["candidates"]] == [c1]
    assert only_rejected["status_counts"] == out["status_counts"] and only_rejected["stages"] == out["stages"]
    assert client.get(f"/drives/{did}/pipeline?status=bogus", headers=h).status_code == 422
    assert client.get(f"/drives/{uuid.uuid4()}/pipeline", headers=h).status_code == 404

    # what the overview calls "awaiting_decision" is exactly what advance accepts without an override
    assert decide(client, rounds, "advance", c2, rounds["tech"]).status_code == 200
