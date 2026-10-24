"""Random schedules and random breakages: the repair must always verify cleanly."""
import random

import pytest

from app.scheduler import solve
from app.scheduler.rescue import CurrentInterview, Disruption, DisruptionKind as DK, rescue
from tests.scheduler.helpers import T
from tests.scheduler.test_random import random_instance


def current_from(res):
    return [CurrentInterview(f"iv{n}", iv.candidate_id, iv.stage_id, iv.start, iv.end,
                             iv.room_id, iv.interviewer_ids)
            for n, iv in enumerate(res.interviews)]


@pytest.mark.parametrize("seed", range(40))
def test_rescue_is_valid_and_stable(seed):
    inp = random_instance(seed)
    res = solve(inp)
    current = current_from(res)
    if not current:
        return

    # with nothing broken, nothing should move
    calm = rescue(inp, current, [])
    assert calm.moves == () and calm.dropped == ()

    rng = random.Random(seed)
    pick = rng.choice(current)
    kind, rid = rng.choice([
        (DK.INTERVIEWER_OUT, rng.choice(pick.interviewer_ids)),
        (DK.ROOM_OUT, pick.room_id),
        (DK.CANDIDATE_OUT, pick.candidate_id),
    ])
    d = Disruption(kind, rid, pick.start, pick.end)
    plan = rescue(inp, current, [d])

    assert plan.violations == ()
    ids = {c.id for c in current}
    accounted = ({m.interview_id for m in plan.moves} | {x.interview_id for x in plan.dropped}
                 | set(plan.unchanged))
    assert accounted == ids
    assert pick.id in plan.affected
    assert pick.id not in plan.unchanged                       # the hit one always changes
    assert not plan.needs_manual
    # nobody is left on the broken resource
    for iv in plan.new_schedule:
        if kind is DK.ROOM_OUT and iv.room_id == rid:
            assert not (iv.start < d.end and d.start < iv.end)
        if kind is DK.INTERVIEWER_OUT and rid in iv.interviewer_ids:
            assert not (iv.start < d.end and d.start < iv.end)
        if kind is DK.CANDIDATE_OUT and iv.candidate_id == rid:
            assert not (iv.start < d.end and d.start < iv.end)
