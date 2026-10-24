from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.scheduler import (
    CandidateSpec, InterviewerSpec, RoomSpec, ScheduleInput, SchedulerConfig,
    StageSpec, Weights, Window,
)

UTC = timezone.utc
DAY0 = datetime(2026, 11, 2, tzinfo=UTC)  # a Monday


def T(hour: int, minute: int = 0, day: int = 0) -> datetime:
    return DAY0 + timedelta(days=day, hours=hour, minutes=minute)


def W(h1: int, h2: int, day: int = 0, m1: int = 0, m2: int = 0) -> Window:
    return Window(T(h1, m1, day), T(h2, m2, day))


def stage(id="s1", order=1, minutes=30, panel=1, skills=()) -> StageSpec:
    return StageSpec(id, order, minutes, panel, frozenset(skills), name=str(id))


def cand(id, stages=("s1",), windows=None, not_before=None) -> CandidateSpec:
    return CandidateSpec(id, tuple(stages), tuple(windows or [W(9, 17)]), not_before)


def intv(id, skills=(), windows=None, cap=8) -> InterviewerSpec:
    return InterviewerSpec(id, frozenset(skills), tuple(windows or [W(9, 17)]), cap)


def room(id, capacity=3) -> RoomSpec:
    return RoomSpec(id, capacity, name=str(id))


def make(stages, cands, intvs, rooms, existing=(), days=1, **cfg) -> ScheduleInput:
    cfg.setdefault("time_limit_seconds", 20.0)
    config = SchedulerConfig(horizon_start=T(0), horizon_end=T(0, day=days), **cfg)
    return ScheduleInput(tuple(stages), tuple(cands), tuple(intvs), tuple(rooms), config,
                         tuple(existing))
