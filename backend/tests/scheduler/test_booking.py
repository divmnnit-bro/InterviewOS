from datetime import timedelta

from app.scheduler import ExistingBooking
from app.scheduler.booking import offer_slots, place, recheck

from .helpers import T, W, cand, intv, make, room, stage


def one(**kw):
    return make([stage(minutes=30)], [cand("c1")], [intv("a"), intv("b")], [room("r")], **kw)


def test_offers_start_at_the_first_free_slot_and_respect_the_grid():
    offers = offer_slots(one(), "c1", "s1", limit=3)
    assert [o.start for o in offers] == [T(9), T(9, 15), T(9, 30)]
    assert all(o.end - o.start == timedelta(minutes=30) for o in offers)


def test_existing_booking_removes_overlapping_slots_only():
    busy = ExistingBooking(T(9), T(10), candidate_id="other", room_id="r", interviewer_ids=("a",))
    offers = offer_slots(one(existing=[busy]), "c1", "s1", limit=2)
    assert offers[0].start == T(10)            # the only room is taken until 10:00


def test_daily_capacity_blocks_a_slot_even_when_the_interviewer_is_free():
    inp = make([stage()], [cand("c1")], [intv("a", cap=1)], [room("r")],
               existing=[ExistingBooking(T(9), T(9, 30), "x", "other-room", ("a",))])
    assert offer_slots(inp, "c1", "s1") == []


def test_place_picks_room_and_panel_and_passes_recheck():
    inp = one()
    p = place(inp, "c1", "s1", T(9, 30))
    assert p and p.room_id == "r" and len(p.interviewer_ids) == 1 and p.start == T(9, 30)
    assert recheck(inp, p) == []


def test_place_rejects_off_grid_unavailable_and_taken_slots():
    inp = one()
    assert place(inp, "c1", "s1", T(9, 10)) is None          # not on the 15-minute grid
    assert place(inp, "c1", "s1", T(8, 0)) is None           # nobody is available yet
    assert place(inp, "c1", "s1", T(16, 45)) is None         # would end after everyone leaves
    busy = ExistingBooking(T(9), T(9, 30), "x", "r", ("a",))
    assert place(one(existing=[busy]), "c1", "s1", T(9)) is None


def test_recheck_catches_a_slot_taken_after_it_was_offered():
    stale = one()
    p = place(stale, "c1", "s1", T(9))
    taken = one(existing=[ExistingBooking(T(9), T(9, 30), "x", "r", ("a", "b"))])
    problems = recheck(taken, p)
    assert any("double booked" in x for x in problems)


def test_recheck_catches_availability_withdrawn_after_it_was_offered():
    p = place(one(), "c1", "s1", T(9))
    shrunk = make([stage(minutes=30)], [cand("c1", windows=[W(12, 13)])], [intv("a"), intv("b")], [room("r")])
    assert any("candidate not available" in x for x in recheck(shrunk, p))


def test_interviewer_rest_buffer_applies_to_self_booking():
    busy = ExistingBooking(T(9), T(9, 30), candidate_id="x", room_id="other", interviewer_ids=("a",))
    inp = make([stage(minutes=30)], [cand("c1")], [intv("a")], [room("r")],
               existing=[busy], interviewer_buffer_minutes=30)
    assert offer_slots(inp, "c1", "s1", limit=1)[0].start == T(10)     # 09:30 + 30 min rest
    assert place(inp, "c1", "s1", T(9, 30)) is None
