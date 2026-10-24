"""The greedy plan (solver hint and timeout fallback) must itself be valid, and a
mid-sized drive must come out complete and fast."""
import pytest

from app.scheduler import SolveStatus, solve
from app.scheduler.greedy import greedy_plan
from app.scheduler.prepare import prepare
from app.scheduler.solver import _fallback
from app.scheduler.verify import verify
from tests.scheduler.helpers import W, cand, intv, make, room, stage
from tests.scheduler.test_random import random_instance


@pytest.mark.parametrize("seed", range(40))
def test_greedy_fallback_is_always_valid(seed):
    inp = random_instance(seed)
    prep = prepare(inp)
    plan = greedy_plan(prep, {r.id: r.capacity for r in inp.rooms},
                       {i.id: i.capacity_per_day for i in inp.interviewers})
    res = _fallback(prep, prep.requests, plan, 0.0)
    assert verify(inp, res) == []
    assert res.status in (SolveStatus.HEURISTIC, SolveStatus.UNKNOWN)
    assert all(u.reasons for u in res.unscheduled)


def test_mid_sized_drive_is_complete_and_valid():
    days = 2
    wins = [W(9, 17, day=d) for d in range(days)]
    inp = make([stage("s1", 1, 30, 2)],
               [cand(f"c{n}", windows=wins) for n in range(80)],
               [intv(f"i{n}", windows=wins, cap=8) for n in range(12)],
               [room(f"r{n}", 4) for n in range(5)],
               days=days, time_limit_seconds=4.0)
    res = solve(inp)
    assert verify(inp, res) == []
    assert res.complete and len(res.interviews) == 80
