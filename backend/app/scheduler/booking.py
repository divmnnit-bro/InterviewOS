"""Self-booking: which slots can one candidate take, and is a chosen slot still valid?

Pure logic, no database. The input is an ordinary `ScheduleInput` that holds ONE candidate
(the one booking) and every booking already occupying a resource in `existing`.

    offer_slots(inp, cid, sid)          -> slots the candidate could take right now
    place(inp, cid, sid, start)         -> the interview that would be created, or None
    recheck(inp, proposed)              -> violations from the independent checker ([] = valid)

`place` picks the room and panel; `recheck` is what makes a confirmation safe: it runs the same
independent checker used for solver output (availability, skills, room size, overlaps,
interviewer rest buffer, daily limits) against the state as it is *now*.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.scheduler import windows as W
from app.scheduler.prepare import Prepared, Request, prepare
from app.scheduler.types import (
    Id,
    ProposedInterview,
    ScheduleInput,
    ScheduleResult,
    SolveStatus,
)
from app.scheduler.verify import verify


@dataclass(frozen=True)
class Offer:
    start: datetime
    end: datetime


def _request(prep: Prepared, candidate_id: Id, stage_id: Id) -> Request | None:
    for r in prep.requests:
        if r.candidate.id == candidate_id and r.stage.id == stage_id:
            return r
    return None


def _in(spans: list[tuple[int, int]], x: int) -> bool:
    return any(a <= x < b for a, b in spans)


def _place_slot(
    inp: ScheduleInput, prep: Prepared, req: Request, x: int
) -> ProposedInterview | None:
    caps = {i.id: i.capacity_per_day for i in inp.interviewers}
    rooms = [rid for rid, sp in req.room_starts.items() if _in(sp, x)]
    if not rooms:
        return None
    day = prep.day_of[x]
    ok = [
        iid for iid, sp in req.interviewer_starts.items()
        if _in(sp, x) and prep.used_per_day.get((iid, day), 0) < caps[iid]
    ]
    if len(ok) < req.stage.panel_size:
        return None
    room_cap = {r.id: r.capacity for r in inp.rooms}
    room = min(rooms, key=lambda k: (room_cap[k], str(k)))            # smallest adequate room
    panel = sorted(ok, key=lambda k: (prep.existing_load.get(k, 0), str(k)))[: req.stage.panel_size]
    start = prep.slot_to_dt(x)
    return ProposedInterview(
        candidate_id=req.candidate.id,
        stage_id=req.stage.id,
        start=start,
        end=start + timedelta(minutes=req.stage.duration_minutes),
        room_id=room,
        interviewer_ids=tuple(panel),
    )


def offer_slots(
    inp: ScheduleInput, candidate_id: Id, stage_id: Id, *,
    limit: int = 50, after: datetime | None = None,
) -> list[Offer]:
    """Earliest-first start times at which a room, a full panel and the candidate are all free."""
    prep = prepare(inp)
    req = _request(prep, candidate_id, stage_id)
    if req is None or req.reasons or not req.starts:
        return []
    lo = prep.ceil_slot(after) if after else 0
    out: list[Offer] = []
    for s, e in req.starts:
        for x in range(max(s, lo), e):
            p = _place_slot(inp, prep, req, x)
            if p:
                out.append(Offer(p.start, p.end))
                if len(out) >= limit:
                    return out
    return out


def place(
    inp: ScheduleInput, candidate_id: Id, stage_id: Id, start: datetime
) -> ProposedInterview | None:
    """The interview that booking `start` would create, or None if that slot is not available."""
    prep = prepare(inp)
    req = _request(prep, candidate_id, stage_id)
    if req is None or req.reasons or not req.starts:
        return None
    x = prep.floor_slot(start)
    if x < 0 or x >= prep.n_slots or prep.slot_to_dt(x) != start:
        return None                      # not on the slot grid
    if not _in(req.starts, x):
        return None
    return _place_slot(inp, prep, req, x)


def recheck(inp: ScheduleInput, proposed: ProposedInterview) -> list[str]:
    """Run the independent checker on this one interview against the current state."""
    return verify(
        inp,
        ScheduleResult(status=SolveStatus.FEASIBLE, interviews=(proposed,), unscheduled=()),
    )
