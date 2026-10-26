from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import (
    DriveCandidate,
    DriveCandidateStatus,
    Evaluation,
    Interview,
    InterviewStage,
    InterviewStatus,
    PanelAssignment,
    Recommendation,
    RecruitmentDrive,
    User,
    UserRole,
)
from app.services.ai.copilot import (
    ask_recruitment_query,
    generate_candidate_summary,
    generate_drive_brief,
    generate_interview_kit,
)
from app.schemas.ai import (
    AskRecruitmentDataRequest,
    CandidateSummaryRequest,
    DriveBriefRequest,
    InterviewKitRequest,
)
from app.services.ai.providers import DeterministicLocalProvider

from .conftest import PASSWORD, iso, login, make_user


@pytest.fixture(autouse=True)
def deterministic_ai_provider(monkeypatch):
    """Keep API tests offline and prevent accidental use of a developer API key."""
    monkeypatch.setattr(
        "app.services.ai.copilot.get_llm_provider",
        lambda: DeterministicLocalProvider(),
    )


def test_generate_interview_kit_sync(client, db, drive, coordinator):
    did = drive["id"]
    h = coordinator

    # Fetch stage
    stage = db.scalars(select(InterviewStage).where(InterviewStage.drive_id == did)).first()

    req = {
        "drive_id": did,
        "stage_id": str(stage.id) if stage else None,
        "topic": "Python & Distributed Systems",
        "difficulty": "intermediate",
        "job_description": "Senior Platform Engineer working on asynchronous task pipelines",
        "required_skills": ["python", "redis"],
        "async_mode": False,
    }

    r = client.post("/ai/interview-kit", headers=h, json=req)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["topic"] == "Python & Distributed Systems"
    assert out["difficulty"] == "intermediate"
    assert len(out["coding_questions"]) >= 1
    cq = out["coding_questions"][0]
    assert cq["title"] and cq["description"]
    assert len(cq["constraints"]) > 0
    assert len(cq["sample_inputs_outputs"]) > 0
    assert cq["evaluation_rubric"]

    assert len(out["system_design_scenarios"]) >= 1
    sd = out["system_design_scenarios"][0]
    assert sd["title"] and sd["problem_statement"]
    assert len(sd["functional_requirements"]) > 0
    assert len(sd["non_functional_requirements"]) > 0

    assert len(out["behavioral_questions"]) >= 1
    assert out["rubric_template"]
    assert out["is_ai_generated"] is False
    assert out["provider_used"] == "deterministic"


def test_generate_interview_kit_async(client, db, drive, coordinator):
    did = drive["id"]
    h = coordinator

    req = {
        "drive_id": did,
        "topic": "Algorithms & Optimization",
        "difficulty": "advanced",
        "async_mode": True,
    }

    r = client.post("/ai/interview-kit", headers=h, json=req)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["job_id"] is not None

    # Poll job status
    job_id = out["job_id"]
    jr = client.get(f"/jobs/{job_id}", headers=h)
    assert jr.status_code == 200
    job_data = jr.json()
    assert job_data["job_type"] == "ai_interview_kit"
    assert job_data["status"] in ("queued", "running", "completed")


def test_interview_kit_requires_coordinator(client, db, drive):
    did = drive["id"]
    u = make_user(db, "cand_ai@example.com", UserRole.CANDIDATE)
    h = login(client, "cand_ai@example.com")
    r = client.post("/ai/interview-kit", headers=h, json={"drive_id": did})
    assert r.status_code == 403


def test_drive_briefing(client, db, published, coordinator):
    did = published["id"]
    h = coordinator

    r = client.post("/ai/drive-brief", headers=h, json={"drive_id": did})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["drive_id"] == did
    assert out["candidate_counts"]["total_enrolled"] == 3
    assert out["candidate_counts"]["active_in_pipeline"] == 3
    assert len(out["upcoming_rounds"]) >= 1
    assert out["executive_summary"]
    assert isinstance(out["scheduling_conflicts_and_risks"], list)
    assert isinstance(out["pending_actions"], list)
    assert out["is_ai_generated"] is False


def test_candidate_ai_summary(client, db, published, coordinator):
    did = published["id"]
    cid = published["candidates"][0]
    h = coordinator

    r = client.post("/ai/candidate-summary", headers=h, json={"drive_id": did, "candidate_id": cid})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["candidate_id"] == cid
    assert out["pipeline_status"] == "active"
    assert out["progression_readiness"]
    assert len(out["recurring_strengths"]) > 0
    assert "human" in out["disclaimer"].lower()
    assert out["is_ai_generated"] is False


def test_ask_recruitment_copilot(client, db, published, coordinator):
    did = published["id"]
    h = coordinator

    # Ask for awaiting evaluation
    r1 = client.post("/ai/ask", headers=h, json={"drive_id": did, "question": "Which candidates are awaiting evaluation?"})
    assert r1.status_code == 200, r1.text
    out1 = r1.json()
    assert out1["intent"] == "awaiting_evaluations"
    assert out1["answer"]
    assert out1["data_points_analyzed"] == len(out1["data_points"])
    assert out1["suggested_followups"]

    # Ask for interviewer workload
    r2 = client.post("/ai/ask", headers=h, json={"question": "Which interviewers have the highest workload?"})
    assert r2.status_code == 200, r2.text
    out2 = r2.json()
    assert out2["intent"] == "interviewer_workload"
    assert len(out2["data_points"]) >= 1

    r3 = client.post("/ai/ask", headers=h, json={"question": "What is the scheduling status of our drives?"})
    assert r3.status_code == 200, r3.text
    assert r3.json()["intent"] == "schedule_status"


def test_candidate_cannot_query_recruitment_data(client, db):
    make_user(db, "candidate_private@example.com", UserRole.CANDIDATE)
    headers = login(client, "candidate_private@example.com")

    response = client.post("/ai/ask", headers=headers, json={"question": "Which candidates are selected?"})

    assert response.status_code == 403


def test_drive_brief_ai_context_contains_only_aggregate_metrics(client, db, published, coordinator, monkeypatch):
    captured = {}

    class FakeProvider:
        name = "openai"
        model = "test-model"

        def ask_text(self, prompt, system_prompt=""):
            captured["prompt"] = prompt
            return "Aggregate summary from verified metrics."

    monkeypatch.setattr("app.services.ai.copilot.get_llm_provider", lambda: FakeProvider())
    response = client.post("/ai/drive-brief", headers=coordinator, json={"drive_id": published["id"]})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["is_ai_generated"] is True
    assert payload["provider_used"] == "openai"
    assert payload["executive_summary"] == "Aggregate summary from verified metrics."
    assert "@" not in captured["prompt"]
    assert published["id"] not in captured["prompt"]
    drive = db.get(RecruitmentDrive, published["id"])
    assert drive.title not in captured["prompt"]
