from datetime import datetime

import pytest

from app.scheduler import InvalidScheduleInput, SchedulerConfig, solve
from app.scheduler.types import ScheduleInput, Window
from tests.scheduler.helpers import T, W, cand, intv, make, room, stage


def problems(inp):
    with pytest.raises(InvalidScheduleInput) as ei:
        solve(inp)
    return ei.value.problems


def test_valid_input_passes():
    solve(make([stage()], [cand("c1")], [intv("a")], [room("r")]))


def test_naive_datetimes_rejected():
    bad = cand("c1", windows=[Window(datetime(2026, 11, 2, 9), datetime(2026, 11, 2, 10))])
    assert any("naive" in p for p in problems(make([stage()], [bad], [intv("a")], [room("r")])))


def test_duplicates_unknown_stage_and_bad_numbers_all_reported():
    inp = make(
        [stage("s1", 1, minutes=0), stage("s1", 1, panel=0)],
        [cand("c1", stages=("nope",)), cand("c1")],
        [intv("a", cap=0)], [room("r", 0), room("r", 2)],
    )
    p = " | ".join(problems(inp))
    for needle in ("duplicate stage id", "duplicate stage order_index", "duplicate candidate id",
                   "duplicate room id", "unknown stage", "duration_minutes", "panel_size",
                   "capacity must be positive", "capacity_per_day"):
        assert needle in p, needle


def test_window_ending_before_start():
    bad = cand("c1", windows=[Window(T(10), T(9))])
    assert any("ends before" in p for p in problems(make([stage()], [bad], [intv("a")], [room("r")])))


def test_bad_config():
    inp = ScheduleInput((stage(),), (), (), (),
                        SchedulerConfig(T(10), T(9), slot_minutes=0, timezone="Mars/Base"))
    p = " | ".join(problems(inp))
    assert "horizon_end" in p and "slot_minutes" in p and "timezone" in p
