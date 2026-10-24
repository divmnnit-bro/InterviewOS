from datetime import timedelta

import pytest

from app.scheduler import InvalidScheduleInput, SolveStatus
from app.scheduler.rescue import (
    Change, CurrentInterview, Disruption, DisruptionKind as DK, rescue,
)
from tests.scheduler.helpers import T, W, cand, intv, make, room, stage


def cur(id, cid, start, rid="r1", panel=("a",), minutes=30, stage_id="s1", locked=False):
    return CurrentInterview(id, cid, stage_id, start, start + timedelta(minutes=minutes),
                            rid, tuple(panel), locked)


def out(kind, rid, s, e):
    return Disruption(kind, rid, s, e)


def test_no_disruption_changes_nothing():
    inp = make([stage()], [cand("c1"), cand("c2")], [intv("a"), intv("b")], [room("r1")])
    plan = rescue(inp, [cur("i1", "c1", T(9)), cur("i2", "c2", T(9, 30), panel=("b",))], [])
    assert plan.moves == () and set(plan.unchanged) == {"i1", "i2"} and plan.fully_repaired
    assert plan.violations == ()


def test_far_away_disruption_changes_nothing():
    inp = make([stage()], [cand("c1")], [intv("a")], [room("r1")])
    plan = rescue(inp, [cur("i1", "c1", T(9))], [out(DK.INTERVIEWER_OUT, "a", T(14), T(15))])
    assert plan.moves == () and plan.affected == ()


def test_sick_interviewer_is_swapped_without_telling_the_candidate():
    inp = make([stage()], [cand("c1")], [intv("a"), intv("b")], [room("r1")])
    plan = rescue(inp, [cur("i1", "c1", T(9))], [out(DK.INTERVIEWER_OUT, "a", T(9), T(12))])
    (mv,) = plan.moves
    assert mv.changes == {Change.PANEL} and mv.new.interviewer_ids == ("b",)
    assert mv.old.start == mv.new.start and not mv.notifies_candidate
    assert plan.candidates_to_notify == () and set(plan.interviewers_to_notify) == {"a", "b"}
    assert plan.violations == ()


def test_closed_room_is_swapped_and_candidate_notified():
    inp = make([stage()], [cand("c1")], [intv("a")], [room("r1"), room("r2")])
    plan = rescue(inp, [cur("i1", "c1", T(9))], [out(DK.ROOM_OUT, "r1", T(8), T(18))])
    (mv,) = plan.moves
    assert mv.changes == {Change.ROOM} and mv.new.room_id == "r2"
    assert plan.candidates_to_notify == ("c1",)


def test_smallest_possible_time_shift():
    inp = make([stage()], [cand("c1")], [intv("a")], [room("r1")])
    plan = rescue(inp, [cur("i1", "c1", T(9))], [out(DK.INTERVIEWER_OUT, "a", T(9), T(9, 30))])
    (mv,) = plan.moves
    assert mv.changes == {Change.TIME} and mv.new.start == T(9, 30)


def test_candidate_out_moves_only_that_candidate():
    inp = make([stage()], [cand("c1"), cand("c2")], [intv("a"), intv("b")], [room("r1"), room("r2")])
    plan = rescue(inp, [cur("i1", "c1", T(9)), cur("i2", "c2", T(9), rid="r2", panel=("b",))],
                  [out(DK.CANDIDATE_OUT, "c1", T(9), T(10))])
    assert [m.interview_id for m in plan.moves] == ["i1"] and plan.unchanged == ("i2",)
    assert plan.moves[0].new.start >= T(10)


def test_ripple_moves_an_unaffected_interview_rather_than_dropping_one():
    # c1 can only do 9:00-10:00, c2 only 9:30-10:30; a is free 9:00-10:30.
    # a is out 9:00-9:30: c1 must take 9:30, which pushes c2 (not hit) to 10:00.
    inp = make([stage()],
               [cand("c1", windows=[W(9, 10)]), cand("c2", windows=[W(9, 10, m1=30, m2=30)])],
               [intv("a", windows=[W(9, 10, m2=30)])], [room("r1")])
    plan = rescue(inp, [cur("i1", "c1", T(9)), cur("i2", "c2", T(9, 30))],
                  [out(DK.INTERVIEWER_OUT, "a", T(9), T(9, 30))])
    by = {m.interview_id: m for m in plan.moves}
    assert by["i1"].new.start == T(9, 30) and by["i1"].directly_affected
    assert by["i2"].new.start == T(10) and not by["i2"].directly_affected
    assert [m.interview_id for m in plan.collateral] == ["i2"]
    assert plan.dropped == () and plan.fully_repaired and plan.violations == ()
    assert set(plan.candidates_to_notify) == {"c1", "c2"}


def test_unfixable_interview_is_dropped_with_reasons():
    inp = make([stage()], [cand("c1")], [intv("a")], [room("r1")])
    plan = rescue(inp, [cur("i1", "c1", T(9))], [out(DK.INTERVIEWER_OUT, "a", T(0), T(23))])
    (d,) = plan.dropped
    assert d.interview_id == "i1" and d.reasons and not plan.fully_repaired
    assert plan.candidates_to_notify == ("c1",) and plan.new_schedule == ()


def test_dropped_only_when_nothing_else_is_possible():
    # one slot left for two interviews: exactly one survives, the other is dropped
    inp = make([stage()], [cand("c1", windows=[W(9, 10)]), cand("c2", windows=[W(9, 10)])],
               [intv("a", windows=[W(9, 10)])], [room("r1")])
    plan = rescue(inp, [cur("i1", "c1", T(9)), cur("i2", "c2", T(9, 30))],
                  [out(DK.INTERVIEWER_OUT, "a", T(9, 30), T(10))])
    assert len(plan.dropped) == 1 and len(plan.new_schedule) == 1


def test_locked_interview_never_moves_and_is_flagged_if_hit():
    inp = make([stage()], [cand("c1"), cand("c2")], [intv("a")], [room("r1")])
    plan = rescue(inp, [cur("i1", "c1", T(9), locked=True), cur("i2", "c2", T(9, 30))],
                  [out(DK.INTERVIEWER_OUT, "a", T(9), T(9, 30))])
    assert plan.needs_manual == ("i1",) and not plan.fully_repaired
    assert all(m.interview_id != "i1" for m in plan.moves)


def test_started_interviews_are_frozen_and_nothing_moves_into_the_past():
    inp = make([stage()], [cand("c1"), cand("c2")], [intv("a")], [room("r1")])
    now = T(10)
    plan = rescue(inp, [cur("past", "c1", T(9)), cur("soon", "c2", T(11))],
                  [out(DK.INTERVIEWER_OUT, "a", T(11), T(11, 30))], now=now)
    assert [m.interview_id for m in plan.moves] == ["soon"]
    mv = plan.moves[0]
    assert mv.new.start >= now                                   # never into the past
    assert abs(mv.new.start - mv.old.start) == timedelta(minutes=30)   # smallest shift
    assert plan.unchanged == () and plan.needs_manual == ()


def test_locked_bookings_block_the_repair():
    inp = make([stage()], [cand("c1"), cand("c2")], [intv("a")], [room("r1")])
    plan = rescue(inp, [cur("i1", "c1", T(9)), cur("i2", "c2", T(9, 30), locked=True)],
                  [out(DK.INTERVIEWER_OUT, "a", T(9), T(9, 30))])
    assert plan.moves[0].new.start >= T(10) and plan.violations == ()


def test_invalid_current_schedule_is_rejected():
    inp = make([stage()], [cand("c1")], [intv("a")], [room("r1")])
    with pytest.raises(InvalidScheduleInput) as ei:
        rescue(inp, [cur("i1", "c1", T(9, 5)), cur("i1", "c1", T(9), minutes=45),
                     cur("i3", "nobody", T(9))], [])
    text = " ".join(ei.value.problems)
    assert "slot grid" in text and "duplicate id" in text and "unknown" in text and "length" in text
