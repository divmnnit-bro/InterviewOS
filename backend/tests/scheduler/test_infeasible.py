"""Requests that can never be scheduled get exact structural reasons."""
from app.scheduler import ReasonCode as RC
from app.scheduler import solve
from app.scheduler.verify import verify
from tests.scheduler.helpers import W, cand, intv, make, room, stage


def reasons(inp, cid="c1"):
    res = solve(inp)
    assert verify(inp, res) == []
    (u,) = [u for u in res.unscheduled if u.candidate_id == cid]
    return {r.code for r in u.reasons}, res


def test_no_qualified_interviewer():
    inp = make([stage(skills=["ml"])], [cand("c1")], [intv("a", skills=["java"])], [room("r")])
    codes, res = reasons(inp)
    assert codes == {RC.NO_QUALIFIED_INTERVIEWERS} and not res.interviews


def test_not_enough_qualified_for_panel():
    inp = make([stage(panel=3, skills=["java"])], [cand("c1")],
               [intv("a", ["java"]), intv("b", ["java"]), intv("c", ["go"])], [room("r", 5)])
    codes, _ = reasons(inp)
    assert codes == {RC.NOT_ENOUGH_QUALIFIED_INTERVIEWERS}


def test_room_too_small():
    inp = make([stage(panel=3)], [cand("c1")], [intv(x) for x in "abc"], [room("r", 3)])
    codes, _ = reasons(inp)
    assert codes == {RC.NO_ROOM_LARGE_ENOUGH}


def test_candidate_without_availability():
    inp = make([stage()], [cand("c1", windows=[W(9, 10, day=3)])], [intv("a")], [room("r")])
    codes, _ = reasons(inp)
    assert codes == {RC.CANDIDATE_NO_AVAILABILITY}


def test_candidate_windows_too_short():
    inp = make([stage(minutes=60)], [cand("c1", windows=[W(9, 9, m2=30), W(11, 11, m2=45)])],
               [intv("a")], [room("r")])
    codes, _ = reasons(inp)
    assert codes == {RC.CANDIDATE_WINDOWS_TOO_SHORT}


def test_interviewer_and_candidate_never_free_together():
    inp = make([stage()], [cand("c1", windows=[W(9, 11)])],
               [intv("a", windows=[W(13, 17)])], [room("r")])
    codes, _ = reasons(inp)
    assert codes == {RC.NO_INTERVIEWER_OVERLAP}


def test_panel_members_never_free_at_same_time():
    inp = make([stage(panel=2)], [cand("c1")],
               [intv("a", windows=[W(9, 11)]), intv("b", windows=[W(12, 14)])], [room("r", 3)])
    codes, _ = reasons(inp)
    assert codes == {RC.NO_INTERVIEWER_OVERLAP}


def test_room_and_panel_never_line_up():
    from app.scheduler import ExistingBooking
    from tests.scheduler.helpers import T
    inp = make([stage()], [cand("c1", windows=[W(9, 10)])], [intv("a")], [room("r")],
               existing=[ExistingBooking(T(9), T(10), room_id="r")])
    codes, _ = reasons(inp)
    assert codes == {RC.NO_ROOM_OVERLAP}


def test_several_independent_problems_are_all_reported():
    inp = make([stage(panel=2, skills=["ml"])], [cand("c1")], [intv("a")], [room("r", 2)])
    codes, _ = reasons(inp)
    assert codes == {RC.NO_QUALIFIED_INTERVIEWERS, RC.NO_ROOM_LARGE_ENOUGH}


def test_later_round_blamed_on_the_earlier_one():
    stages = [stage("coding", 1, skills=["ml"]), stage("hr", 2)]
    inp = make(stages, [cand("c1", stages=("coding", "hr"))], [intv("a")], [room("r")])
    res = solve(inp)
    got = {u.stage_id: {r.code for r in u.reasons} for u in res.unscheduled}
    assert got == {"coding": {RC.NO_QUALIFIED_INTERVIEWERS},
                   "hr": {RC.PREVIOUS_ROUND_UNSCHEDULED}}
    assert not res.interviews


def test_one_bad_candidate_does_not_block_the_others():
    inp = make([stage()], [cand("ok"), cand("nobody", windows=[W(9, 10, day=2)])],
               [intv("a")], [room("r")], days=1)
    res = solve(inp)
    assert [iv.candidate_id for iv in res.interviews] == ["ok"]
    assert [u.candidate_id for u in res.unscheduled] == ["nobody"]
