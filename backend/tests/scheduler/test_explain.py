from app.scheduler import ReasonCode as RC
from app.scheduler import solve
from app.scheduler.explain import BlockerKind as BK
from app.scheduler.explain import FixKind as FK
from app.scheduler.explain import explain
from tests.scheduler.helpers import W, cand, intv, make, room, stage


def kinds(e):
    return {f.kind for f in e.fixes}


def test_complete_schedule_has_nothing_to_explain():
    inp = make([stage()], [cand("c1")], [intv("a")], [room("r")])
    rep = explain(inp, solve(inp))
    assert rep.explanations == {} and rep.what_ifs == ()


def test_room_bottleneck_names_the_room_and_the_blocking_interview():
    inp = make([stage()], [cand(f"c{n}", windows=[W(9, 10)]) for n in range(3)],
               [intv("a"), intv("b")], [room("r1")])
    res = solve(inp)
    (u,) = res.unscheduled
    e = explain(inp, res).explanations[(u.candidate_id, u.stage_id)]
    assert e.reason_codes == (RC.CAPACITY_CONTENTION,)
    assert [b.kind for b in e.blockers] == [BK.ROOM_BUSY]
    blocker = e.blockers[0]
    assert blocker.resource_id == "r1" and blocker.interviews[0].candidate_id != u.candidate_id
    assert FK.ADD_ROOM in kinds(e)
    assert FK.RAISE_DAILY_CAPACITY not in kinds(e)       # not the real bottleneck
    assert "room 'r1'" in e.summary and "add one more room" in e.summary
    assert all(f.extra_interviews >= 1 for f in e.fixes)


def test_daily_capacity_bottleneck():
    inp = make([stage()], [cand(f"c{n}") for n in range(3)], [intv("a", cap=2)],
               [room("r1"), room("r2")])
    res = solve(inp)
    (u,) = res.unscheduled
    e = explain(inp, res).explanations[(u.candidate_id, u.stage_id)]
    assert BK.INTERVIEWER_DAILY_CAPACITY in {b.kind for b in e.blockers}
    assert FK.RAISE_DAILY_CAPACITY in kinds(e) and FK.ADD_INTERVIEWER in kinds(e)
    assert FK.ADD_ROOM not in kinds(e)
    assert "daily limit of 2" in e.summary


def test_busy_interviewer_is_named():
    inp = make([stage()], [cand(f"c{n}", windows=[W(9, 10)]) for n in range(3)],
               [intv("a")], [room("r1"), room("r2")])
    res = solve(inp)
    (u,) = res.unscheduled
    e = explain(inp, res).explanations[(u.candidate_id, u.stage_id)]
    assert BK.INTERVIEWER_BUSY in {b.kind for b in e.blockers}
    assert FK.ADD_INTERVIEWER in kinds(e) and FK.ADD_ROOM not in kinds(e)


def test_structural_missing_skill_suggests_a_new_interviewer():
    inp = make([stage(skills=["ml"])], [cand("c1")], [intv("a", ["java"])], [room("r")])
    res = solve(inp)
    e = explain(inp, res).explanations[("c1", "s1")]
    assert e.reason_codes == (RC.NO_QUALIFIED_INTERVIEWERS,)
    assert "ml" in e.summary and FK.ADD_INTERVIEWER in kinds(e) and not e.blockers


def test_structural_room_too_small_suggests_a_room():
    inp = make([stage(panel=2)], [cand("c1")], [intv("a"), intv("b")], [room("r", 2)])
    e = explain(inp, solve(inp)).explanations[("c1", "s1")]
    assert kinds(e) == {FK.ADD_ROOM}


def test_candidate_without_availability_suggests_asking_them():
    inp = make([stage()], [cand("c1", windows=[W(9, 10, day=3)])], [intv("a")], [room("r")])
    e = explain(inp, solve(inp)).explanations[("c1", "s1")]
    assert kinds(e) == {FK.WIDEN_CANDIDATE_AVAILABILITY} and e.fixes[0].target_id == "c1"


def test_disjoint_interviewer_suggests_widening_or_adding():
    inp = make([stage()], [cand("c1", windows=[W(9, 11)])], [intv("a", windows=[W(13, 17)])],
               [room("r")])
    e = explain(inp, solve(inp)).explanations[("c1", "s1")]
    assert {FK.WIDEN_INTERVIEWER_AVAILABILITY, FK.WIDEN_CANDIDATE_AVAILABILITY,
            FK.ADD_INTERVIEWER} <= kinds(e)


def test_later_round_gets_fixes_through_the_earlier_one():
    inp = make([stage("coding", 1, skills=["ml"]), stage("hr", 2)],
               [cand("c1", stages=("coding", "hr"))], [intv("a")], [room("r")])
    rep = explain(inp, solve(inp))
    assert RC.PREVIOUS_ROUND_UNSCHEDULED in rep.explanations[("c1", "hr")].reason_codes
    assert FK.ADD_INTERVIEWER in kinds(rep.explanations[("c1", "hr")])


def test_what_if_budget_is_respected():
    inp = make([stage()], [cand(f"c{n}", windows=[W(9, 10)]) for n in range(3)],
               [intv("a"), intv("b")], [room("r1")])
    rep = explain(inp, solve(inp), max_whatifs=1)
    assert len(rep.what_ifs) == 1 and rep.budget_exhausted
