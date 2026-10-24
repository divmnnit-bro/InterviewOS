from datetime import timedelta

from app.scheduler import ExistingBooking, SolveStatus, Weights, solve
from app.scheduler.verify import verify
from tests.scheduler.helpers import T, W, cand, intv, make, room, stage


def run(inp):
    res = solve(inp)
    assert verify(inp, res) == [], verify(inp, res)
    return res


def test_nothing_to_schedule():
    res = solve(make([stage()], [], [intv("i1")], [room("r1")]))
    assert res.status == SolveStatus.NOTHING_TO_SCHEDULE and res.complete


def test_single_interview_goes_as_early_as_possible():
    res = run(make([stage()], [cand("c1", windows=[W(10, 12)])], [intv("i1")], [room("r1")]))
    assert res.status == SolveStatus.OPTIMAL and res.complete
    (iv,) = res.interviews
    assert iv.start == T(10) and iv.end == T(10, 30)
    assert iv.interviewer_ids == ("i1",) and iv.room_id == "r1"


def test_one_room_one_panel_serialises_candidates():
    inp = make([stage()], [cand(f"c{n}") for n in range(4)], [intv("i1")], [room("r1")])
    res = run(inp)
    assert res.complete and len(res.interviews) == 4
    assert [iv.start for iv in res.interviews] == [T(9), T(9, 30), T(10), T(10, 30)]


def test_parallel_when_resources_allow():
    inp = make([stage()], [cand("c1"), cand("c2")], [intv("i1"), intv("i2")],
               [room("r1"), room("r2")])
    res = run(inp)
    assert {iv.start for iv in res.interviews} == {T(9)}


def test_skills_pick_the_qualified_interviewer():
    inp = make([stage(skills=["python"])], [cand("c1")],
               [intv("generalist", skills=["java"]), intv("py", skills=["Python", "sql"])],
               [room("r1")])
    (iv,) = run(inp).interviews
    assert iv.interviewer_ids == ("py",)


def test_panel_needs_all_members_free_simultaneously():
    inp = make([stage(panel=2)], [cand("c1")],
               [intv("a", windows=[W(10, 11)]), intv("b", windows=[W(10, 12)])],
               [room("r1", capacity=3)])
    (iv,) = run(inp).interviews
    assert set(iv.interviewer_ids) == {"a", "b"} and iv.start == T(10)


def test_panel_overlap_window_is_exact():
    # a free 10:00-11:00, b free 10:30-11:30, 30 minute session -> only 10:30 works
    a = intv("a", windows=[W(10, 11)])
    b = intv("b", windows=[W(10, 11, m1=30, m2=30)])
    inp = make([stage(panel=2)], [cand("c1")], [a, b], [room("r1")])
    (iv,) = run(inp).interviews
    assert iv.start == T(10, 30)


def test_room_must_seat_panel_plus_candidate():
    inp = make([stage(panel=2)], [cand("c1")], [intv("a"), intv("b")],
               [room("small", 2), room("big", 3)])
    (iv,) = run(inp).interviews
    assert iv.room_id == "big"


def test_prefers_smallest_adequate_room():
    inp = make([stage()], [cand("c1")], [intv("i1")], [room("huge", 20), room("snug", 2)])
    (iv,) = run(inp).interviews
    assert iv.room_id == "snug"


def test_load_is_balanced_between_equal_interviewers():
    inp = make([stage()], [cand(f"c{n}") for n in range(4)], [intv("a"), intv("b")],
               [room("r1"), room("r2")], weights=Weights(earliness=0))
    res = run(inp)
    assert res.load_per_interviewer == {"a": 2, "b": 2}


def test_scheduling_beats_preferences_even_with_absurd_weights():
    inp = make([stage()], [cand(f"c{n}") for n in range(3)], [intv("a")], [room("r1")],
               weights=Weights(scheduled=1, earliness=10_000, load_balance=10_000))
    assert run(inp).complete


def test_contention_leaves_one_out_with_reason():
    inp = make([stage()], [cand(f"c{n}", windows=[W(9, 10)]) for n in range(3)],
               [intv("a")], [room("r1")])
    res = run(inp)
    assert len(res.interviews) == 2 and len(res.unscheduled) == 1
    assert res.unscheduled[0].reasons[0].code.value == "capacity_contention"


def test_buffer_between_interviewer_sessions():
    inp = make([stage()], [cand("c1"), cand("c2")], [intv("a")], [room("r1")],
               interviewer_buffer_minutes=15)
    res = run(inp)
    assert [iv.start for iv in res.interviews] == [T(9), T(9, 45)]


def test_daily_capacity_pushes_work_to_next_day():
    inp = make([stage()], [cand(f"c{n}", windows=[W(9, 17), W(9, 17, day=1)]) for n in range(3)],
               [intv("a", windows=[W(9, 17), W(9, 17, day=1)], cap=2)], [room("r1")], days=2)
    res = run(inp)
    assert res.complete
    days = sorted(iv.start.day for iv in res.interviews)
    assert days == [2, 2, 3]


def test_daily_capacity_is_a_hard_limit():
    inp = make([stage()], [cand(f"c{n}") for n in range(3)], [intv("a", cap=2)], [room("r1")])
    res = run(inp)
    assert len(res.interviews) == 2 and len(res.unscheduled) == 1


def test_daily_capacity_uses_the_configured_timezone():
    # 17:30-20:30 UTC is 23:00-02:00 IST: two different local days.
    wins = [W(17, 21, m1=30, m2=0)]
    base = dict(stages=[stage(minutes=60)],
                cands=[cand("c1", windows=wins), cand("c2", windows=wins)],
                intvs=[intv("a", windows=wins, cap=1)], rooms=[room("r1")])
    utc = run(make(*base.values()))
    ist = run(make(*base.values(), timezone="Asia/Kolkata"))
    assert len(utc.interviews) == 1
    assert len(ist.interviews) == 2


def test_existing_bookings_are_respected():
    existing = [
        ExistingBooking(T(9), T(10), room_id="r1"),
        ExistingBooking(T(9), T(10), interviewer_ids=("i1",)),
        ExistingBooking(T(9), T(10), candidate_id="c1"),
    ]
    inp = make([stage()], [cand("c1")], [intv("i1"), intv("i2")], [room("r1"), room("r2")],
               existing=existing)
    (iv,) = run(inp).interviews
    # c1 is busy until 10:00, so the earliest start is 10:00
    assert iv.start == T(10)


def test_existing_bookings_count_toward_daily_capacity():
    existing = [ExistingBooking(T(9), T(9, 30), interviewer_ids=("a",), room_id="r2")]
    inp = make([stage()], [cand("c1")], [intv("a", cap=1)], [room("r1"), room("r2")],
               existing=existing)
    res = run(inp)
    assert not res.interviews and res.unscheduled


def test_not_before_is_respected():
    inp = make([stage()], [cand("c1", not_before=T(13))], [intv("a")], [room("r1")])
    (iv,) = run(inp).interviews
    assert iv.start == T(13)


def test_rounds_run_in_order_with_gap():
    stages = [stage("coding", 1, 60), stage("tech", 2, 45)]
    inp = make(stages, [cand("c1", stages=("tech", "coding"))], [intv("a")], [room("r1")],
               min_round_gap_minutes=30)
    res = run(inp)
    by = {iv.stage_id: iv for iv in res.interviews}
    assert by["coding"].start == T(9)
    assert by["tech"].start >= by["coding"].end + timedelta(minutes=30)


def test_same_input_gives_same_schedule():
    inp = make([stage()], [cand(f"c{n}") for n in range(6)], [intv("a"), intv("b")],
               [room("r1"), room("r2")])
    assert solve(inp).interviews == solve(inp).interviews
