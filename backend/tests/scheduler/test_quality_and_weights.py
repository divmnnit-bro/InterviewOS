from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.scheduler import (
    CandidateSpec,
    InterviewerSpec,
    RoomSpec,
    ScheduleInput,
    SchedulerConfig,
    StageSpec,
    Weights,
    Window,
    solve,
)
from app.scheduler.quality import compare_schedules, compute_schedule_quality
from app.scheduler.types import SolveStatus

T0 = datetime(2026, 11, 2, tzinfo=timezone.utc)


def test_schedule_quality_metrics_computation():
    s1 = StageSpec(id="s1", order_index=1, duration_minutes=30, panel_size=1, required_skills=frozenset(["python"]))
    c1 = CandidateSpec(id="c1", stage_ids=("s1",), availability=(Window(T0, T0 + timedelta(hours=8)),))
    c2 = CandidateSpec(id="c2", stage_ids=("s1",), availability=(Window(T0, T0 + timedelta(hours=8)),))
    i1 = InterviewerSpec(id="i1", skills=frozenset(["python"]), availability=(Window(T0, T0 + timedelta(hours=8)),), capacity_per_day=4)
    i2 = InterviewerSpec(id="i2", skills=frozenset(["python"]), availability=(Window(T0, T0 + timedelta(hours=8)),), capacity_per_day=4)
    r1 = RoomSpec(id="r1", capacity=3)

    cfg = SchedulerConfig(horizon_start=T0, horizon_end=T0 + timedelta(hours=8))
    inp = ScheduleInput(stages=(s1,), candidates=(c1, c2), interviewers=(i1, i2), rooms=(r1,), config=cfg)

    result = solve(inp)
    assert result.status == SolveStatus.OPTIMAL
    assert result.complete

    quality = compute_schedule_quality(inp, result)
    assert quality.is_verified is True
    assert quality.hard_constraint_violations == 0
    assert quality.completion_rate == 100.0
    assert quality.scheduled_count == 2
    assert quality.unscheduled_count == 0
    assert quality.room_utilization_percent > 0.0
    assert quality.interviewer_workload_variance >= 0.0

    # Test compare_schedules
    comp = compare_schedules([], list(result.interviews))
    assert comp.added_count == 2
    assert comp.moved_count == 0
    assert comp.cancelled_count == 0


def test_soft_weights_customization():
    s1 = StageSpec(id="s1", order_index=1, duration_minutes=30, panel_size=1, required_skills=frozenset(["python"]))
    c1 = CandidateSpec(id="c1", stage_ids=("s1",), availability=(Window(T0, T0 + timedelta(hours=8)),))
    i1 = InterviewerSpec(id="i1", skills=frozenset(["python"]), availability=(Window(T0, T0 + timedelta(hours=8)),), capacity_per_day=4)
    r1 = RoomSpec(id="r1", capacity=3)

    # High load balance weight
    weights = Weights(scheduled=1_000_000, earliness=50, load_balance=500, room_fit=10)
    cfg = SchedulerConfig(horizon_start=T0, horizon_end=T0 + timedelta(hours=8), weights=weights)
    inp = ScheduleInput(stages=(s1,), candidates=(c1,), interviewers=(i1,), rooms=(r1,), config=cfg)

    result = solve(inp)
    assert result.status == SolveStatus.OPTIMAL
