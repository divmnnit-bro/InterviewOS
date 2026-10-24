"""Random small instances: whatever the solver returns must pass the independent verifier."""
import random

import pytest

from app.scheduler import ExistingBooking, Weights, solve
from app.scheduler.verify import verify
from tests.scheduler.helpers import T, W, cand, intv, make, room, stage

SKILLS = ["python", "java", "sql"]


def random_instance(seed: int):
    rng = random.Random(seed)
    days = rng.choice([1, 2])

    def windows():
        wins = []
        for d in range(days):
            if rng.random() < 0.85:
                a = rng.randint(8, 13)
                wins.append(W(a, a + rng.randint(2, 6), day=d))
        return wins or [W(9, 12)]

    stages = [stage("s1", 1, rng.choice([30, 45, 60]), rng.choice([1, 1, 2]),
                    rng.sample(SKILLS, rng.randint(0, 1))),
              stage("s2", 2, rng.choice([30, 45]), 1, [])]
    cands = [cand(f"c{n}", stages=("s1", "s2") if rng.random() < 0.3 else ("s1",),
                  windows=windows()) for n in range(rng.randint(2, 7))]
    intvs = [intv(f"i{n}", rng.sample(SKILLS, rng.randint(0, 3)), windows(), rng.randint(1, 4))
             for n in range(rng.randint(1, 4))]
    rooms = [room(f"r{n}", rng.randint(2, 4)) for n in range(rng.randint(1, 3))]
    existing = []
    if rng.random() < 0.5:
        existing.append(ExistingBooking(T(9), T(10), room_id="r0",
                                        interviewer_ids=("i0",), candidate_id="other"))
    return make(stages, cands, intvs, rooms, existing, days=days,
                interviewer_buffer_minutes=rng.choice([0, 15]),
                min_round_gap_minutes=rng.choice([0, 30]),
                weights=Weights(), time_limit_seconds=10)


@pytest.mark.parametrize("seed", range(40))
def test_random_instance_is_valid(seed):
    inp = random_instance(seed)
    res = solve(inp)
    assert verify(inp, res) == []
    scheduled = {(i.candidate_id, i.stage_id) for i in res.interviews}
    left = {(u.candidate_id, u.stage_id) for u in res.unscheduled}
    wanted = {(c.id, s) for c in inp.candidates for s in c.stage_ids}
    assert scheduled | left == wanted and not scheduled & left
    assert all(u.reasons for u in res.unscheduled)
