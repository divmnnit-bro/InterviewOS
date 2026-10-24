"""Turn plain input into slot-based requests, and find hopeless ones early.

A "request" is one (candidate, stage) interview that needs placing. Before the
solver runs, each request gets the exact set of start slots at which it could
possibly happen: the candidate is free, enough qualified interviewers are free
at the same moment, and a big-enough room is free. If that set is empty the
request can never be scheduled, and the reasons are recorded here. These are
exact structural reasons, not guesses; the solver only decides who loses when
requests compete for the same resources.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.scheduler import windows as W
from app.scheduler.types import (
    CandidateSpec,
    Id,
    InterviewerSpec,
    Reason,
    ReasonCode,
    ScheduleInput,
    StageSpec,
)

Span = W.Span


@dataclass
class Request:
    index: int
    candidate: CandidateSpec
    stage: StageSpec
    duration_slots: int
    prev: int | None = None                    # index of this candidate's earlier round
    starts: list[Span] = field(default_factory=list)
    interviewer_starts: dict[Id, list[Span]] = field(default_factory=dict)
    room_starts: dict[Id, list[Span]] = field(default_factory=dict)
    reasons: list[Reason] = field(default_factory=list)


@dataclass
class Prepared:
    n_slots: int
    slot_minutes: int
    horizon_start: datetime
    requests: list[Request]
    day_of: list[int]                          # slot -> local-day index
    used_per_day: dict[tuple[Id, int], int]    # existing bookings per interviewer/day
    existing_load: dict[Id, int]
    buffer_slots: int
    gap_slots: int

    def slot_to_dt(self, slot: int) -> datetime:
        return self.horizon_start + timedelta(minutes=slot * self.slot_minutes)

    def floor_slot(self, dt: datetime) -> int:
        return int((dt - self.horizon_start).total_seconds() // (self.slot_minutes * 60))

    def ceil_slot(self, dt: datetime) -> int:
        secs = (dt - self.horizon_start).total_seconds()
        return int(-(-secs // (self.slot_minutes * 60)))


def _spans_to_set(spans: list[Span]) -> set[int]:
    return {x for s, e in spans for x in range(s, e)}


def prepare(inp: ScheduleInput) -> Prepared:
    cfg = inp.config
    hs = cfg.horizon_start
    slot_secs = cfg.slot_minutes * 60
    n = int((cfg.horizon_end - hs).total_seconds() // slot_secs)

    def ceil_slot(dt: datetime) -> int:
        secs = (dt - hs).total_seconds()
        return int(-(-secs // slot_secs))

    def floor_slot(dt: datetime) -> int:
        return int((dt - hs).total_seconds() // slot_secs)

    def ceil_div(a: int, b: int) -> int:
        return -(-a // b)

    buf = ceil_div(cfg.interviewer_buffer_minutes, cfg.slot_minutes)
    gap = ceil_div(cfg.min_round_gap_minutes, cfg.slot_minutes)

    # --- day index per slot (for the daily interviewer capacity)
    tz = cfg.tz
    day_ids: dict = {}
    day_of: list[int] = []
    for x in range(n):
        d = (hs + timedelta(minutes=x * cfg.slot_minutes)).astimezone(tz).date()
        day_of.append(day_ids.setdefault(d, len(day_ids)))

    # --- existing bookings, snapped outward so we never squeeze into a gap
    cand_busy: dict[Id, list[Span]] = {}
    room_busy: dict[Id, list[Span]] = {}
    intv_busy: dict[Id, list[Span]] = {}
    used: dict[tuple[Id, int], int] = {}
    existing_load: dict[Id, int] = {}
    for b in inp.existing:
        s, e = floor_slot(b.start), ceil_slot(b.end)
        if e <= 0 or s >= n:
            continue
        if b.candidate_id is not None:
            cand_busy.setdefault(b.candidate_id, []).append((s, e))
        if b.room_id is not None:
            room_busy.setdefault(b.room_id, []).append((s, e))
        for iid in b.interviewer_ids:
            intv_busy.setdefault(iid, []).append((s - buf, e + buf))
            if 0 <= s < n:
                key = (iid, day_of[s])
                used[key] = used.get(key, 0) + 1
                existing_load[iid] = existing_load.get(iid, 0) + 1

    def free_of(avail, busy: list[Span], lo: int = 0) -> list[Span]:
        spans = [(ceil_slot(w.start), floor_slot(w.end)) for w in avail]
        return W.subtract(W.clip(spans, max(lo, 0), n), busy)

    intv_free = {i.id: free_of(i.availability, intv_busy.get(i.id, [])) for i in inp.interviewers}
    room_free = {
        r.id: W.subtract(
            [(0, n)] if r.availability is None else free_of(r.availability, []),
            room_busy.get(r.id, []),
        )
        for r in inp.rooms
    }
    stage_by_id = {s.id: s for s in inp.stages}

    requests: list[Request] = []
    for cand in inp.candidates:
        lo = ceil_slot(cand.not_before) if cand.not_before else 0
        cfree = free_of(cand.availability, cand_busy.get(cand.id, []), lo)
        prev: Request | None = None
        for st in sorted((stage_by_id[s] for s in cand.stage_ids), key=lambda s: s.order_index):
            d = max(1, ceil_div(st.duration_minutes, cfg.slot_minutes))
            req = Request(len(requests), cand, st, d, prev.index if prev else None)
            _analyse(req, cfree, d, inp.interviewers, intv_free, inp.rooms, room_free, cfg.slot_minutes)
            if prev is not None and prev.reasons and not req.reasons:
                req.reasons.append(Reason(
                    ReasonCode.PREVIOUS_ROUND_UNSCHEDULED,
                    f"round {prev.stage.order_index} cannot be scheduled, so round "
                    f"{st.order_index} has nothing to follow",
                ))
                req.starts, req.interviewer_starts, req.room_starts = [], {}, {}
            requests.append(req)
            prev = req

    return Prepared(n, cfg.slot_minutes, hs, requests, day_of, used, existing_load, buf, gap)


def _analyse(req: Request, cfree, d, interviewers, intv_free, rooms, room_free, slot_min) -> None:
    st = req.stage
    need_min = st.duration_minutes
    cand_starts = W.start_spans(cfree, d)
    qualified: list[InterviewerSpec] = [
        i for i in interviewers
        if {s.lower() for s in st.required_skills} <= {s.lower() for s in i.skills}
    ]
    big_rooms = [r for r in rooms if r.capacity >= st.panel_size + 1]

    # 1. problems that exist on their own
    if not cfree:
        req.reasons.append(Reason(ReasonCode.CANDIDATE_NO_AVAILABILITY,
                                  "candidate has no free time inside the drive window"))
    elif not cand_starts:
        req.reasons.append(Reason(ReasonCode.CANDIDATE_WINDOWS_TOO_SHORT,
                                  f"no free window of the candidate is {need_min} minutes long"))
    if not qualified:
        skills = ", ".join(sorted(st.required_skills)) or "(none)"
        req.reasons.append(Reason(ReasonCode.NO_QUALIFIED_INTERVIEWERS,
                                  f"no interviewer has all required skills: {skills}"))
    elif len(qualified) < st.panel_size:
        req.reasons.append(Reason(ReasonCode.NOT_ENOUGH_QUALIFIED_INTERVIEWERS,
                                  f"panel needs {st.panel_size} interviewers but only "
                                  f"{len(qualified)} are qualified"))
    if not big_rooms:
        req.reasons.append(Reason(ReasonCode.NO_ROOM_LARGE_ENOUGH,
                                  f"needs a room for {st.panel_size + 1} people "
                                  f"(panel plus candidate); none is large enough"))
    if req.reasons:
        return

    # 2. problems that only show when the resources are lined up in time
    i_starts = {i.id: W.start_spans(intv_free[i.id], d) for i in qualified}
    r_starts = {r.id: W.start_spans(room_free[r.id], d) for r in big_rooms}
    i_sets = {k: _spans_to_set(v) for k, v in i_starts.items()}
    r_sets = {k: _spans_to_set(v) for k, v in r_starts.items()}

    feasible: list[int] = []
    some_panel = some_room = False
    for x in sorted(_spans_to_set(cand_starts)):
        panel_ok = sum(x in s for s in i_sets.values()) >= st.panel_size
        room_ok = any(x in s for s in r_sets.values())
        some_panel |= panel_ok
        some_room |= room_ok
        if panel_ok and room_ok:
            feasible.append(x)

    if not feasible:
        if not some_panel:
            req.reasons.append(Reason(
                ReasonCode.NO_INTERVIEWER_OVERLAP,
                f"at no moment when the candidate is free are {st.panel_size} qualified "
                f"interviewer(s) also free for {need_min} minutes"))
        elif not some_room:
            req.reasons.append(Reason(
                ReasonCode.NO_ROOM_OVERLAP,
                "no suitable room is free at any time the candidate and a panel are free"))
        else:
            req.reasons.append(Reason(
                ReasonCode.NO_ROOM_OVERLAP,
                "a panel and a room are each free at times the candidate is free, "
                "but never at the same time"))
        return

    req.starts = W.merge([(x, x + 1) for x in feasible])
    req.interviewer_starts = {
        k: W.intersect(v, req.starts) for k, v in i_starts.items() if W.intersect(v, req.starts)
    }
    req.room_starts = {
        k: W.intersect(v, req.starts) for k, v in r_starts.items() if W.intersect(v, req.starts)
    }
