"""Conflict explanations: why an interview was left out, and what would fix it.

For every unscheduled request this reports

  * the structural reasons already found by `solve` (exact), and
  * for requests that fit on their own but lost to other demand, the *blockers*:
    the best slot they could take and which proposed interviews, rooms or
    daily limits stand in the way, and
  * *verified fixes*: single changes, each tried by actually re-running the
    solver on a relaxed copy of the input. A fix is only listed for a request
    if that re-run schedules it.

Everything works on plain data. Nothing is saved or changed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from app.scheduler.prepare import Prepared, Request, prepare
from app.scheduler.solver import solve
from app.scheduler.types import (
    Id,
    InterviewerSpec,
    ProposedInterview,
    ReasonCode,
    RoomSpec,
    ScheduleInput,
    ScheduleResult,
    Window,
)

Key = tuple[Id, Id]  # (candidate_id, stage_id)
_BIG = 1000


class BlockerKind(str, Enum):
    ROOM_BUSY = "room_busy"
    INTERVIEWER_BUSY = "interviewer_busy"
    INTERVIEWER_DAILY_CAPACITY = "interviewer_daily_capacity"


class FixKind(str, Enum):
    ADD_ROOM = "add_room"
    ADD_INTERVIEWER = "add_interviewer"
    RAISE_DAILY_CAPACITY = "raise_daily_capacity"
    WIDEN_CANDIDATE_AVAILABILITY = "widen_candidate_availability"
    WIDEN_INTERVIEWER_AVAILABILITY = "widen_interviewer_availability"


@dataclass(frozen=True)
class Blocker:
    kind: BlockerKind
    resource_id: Id
    interviews: tuple[ProposedInterview, ...]  # proposed interviews in the way


@dataclass(frozen=True)
class Fix:
    kind: FixKind
    description: str
    target_id: Id | None
    extra_interviews: int      # how many more interviews the whole run schedules


@dataclass(frozen=True)
class Explanation:
    candidate_id: Id
    stage_id: Id
    reason_codes: tuple[ReasonCode, ...]
    summary: str
    best_slot: datetime | None
    blockers: tuple[Blocker, ...]
    fixes: tuple[Fix, ...]


@dataclass(frozen=True)
class WhatIf:
    kind: FixKind
    description: str
    target_id: Id | None
    total_scheduled: int
    rescued: tuple[Key, ...]


@dataclass(frozen=True)
class ExplanationReport:
    explanations: dict[Key, Explanation]
    what_ifs: tuple[WhatIf, ...]
    budget_exhausted: bool = False


def explain(
    inp: ScheduleInput,
    result: ScheduleResult,
    *,
    max_whatifs: int = 30,
    whatif_time_limit: float = 5.0,
) -> ExplanationReport:
    if not result.unscheduled:
        return ExplanationReport({}, ())

    prep = prepare(inp)
    reqs: dict[Key, Request] = {(r.candidate.id, r.stage.id): r for r in prep.requests}
    left = [(u.candidate_id, u.stage_id) for u in result.unscheduled]
    what_ifs, exhausted = _what_ifs(inp, result, prep, reqs, left, max_whatifs, whatif_time_limit)

    tz = inp.config.tz
    info = _proposed_info(prep, result)
    caps = {i.id: i.capacity_per_day for i in inp.interviewers}
    out: dict[Key, Explanation] = {}
    for u in result.unscheduled:
        key = (u.candidate_id, u.stage_id)
        r = reqs[key]
        codes = tuple(x.code for x in u.reasons)
        fixes = tuple(
            Fix(w.kind, w.description, w.target_id, w.total_scheduled - len(result.interviews))
            for w in what_ifs if key in w.rescued
        )
        slot, blockers = (None, ())
        if ReasonCode.CAPACITY_CONTENTION in codes and r.starts:
            slot, blockers = _best_slot(r, prep, info, caps, inp)
        summary = _summary(u, codes, slot, blockers, fixes, prep, tz, caps)
        out[key] = Explanation(
            u.candidate_id, u.stage_id, codes, summary,
            prep.slot_to_dt(slot) if slot is not None else None, blockers, fixes,
        )
    return ExplanationReport(out, tuple(what_ifs), exhausted)


# ------------------------------------------------------------------ blockers


@dataclass
class _P:
    iv: ProposedInterview
    s: int
    e: int
    day: int | None


def _proposed_info(prep: Prepared, result: ScheduleResult) -> list[_P]:
    out = []
    for iv in result.interviews:
        s, e = prep.floor_slot(iv.start), prep.ceil_slot(iv.end)
        out.append(_P(iv, s, e, prep.day_of[s] if 0 <= s < prep.n_slots else None))
    return out


def _in(spans, x: int) -> bool:
    return any(a <= x < b for a, b in spans)


def _best_slot(r: Request, prep: Prepared, info: list[_P], caps, inp):
    """The feasible start needing the fewest proposed interviews to move."""
    d, buf = r.duration_slots, prep.buffer_slots
    best = None
    for x in sorted({x for a, b in r.starts for x in range(a, b)}):
        blockers: list[Blocker] = []
        cost = 0

        # room: a free one, else the one with the fewest proposed interviews in it
        options = []
        for rid, spans in r.room_starts.items():
            if _in(spans, x):
                hits = [p.iv for p in info if p.iv.room_id == rid and p.s < x + d and x < p.e]
                options.append((len(hits), str(rid), rid, hits))
        if options:
            n, _, rid, hits = min(options, key=lambda t: t[:2])
            if n:
                blockers.append(Blocker(BlockerKind.ROOM_BUSY, rid, tuple(hits)))
                cost += n

        # panel: the cheapest interviewers at this slot
        cands = []
        for iid, spans in r.interviewer_starts.items():
            if not _in(spans, x):
                continue
            busy = [p.iv for p in info
                    if iid in p.iv.interviewer_ids and p.s < x + d + buf and x < p.e + buf]
            day = prep.day_of[x]
            same_day = [p.iv for p in info
                        if iid in p.iv.interviewer_ids and p.day == day]
            full = len(same_day) + prep.used_per_day.get((iid, day), 0) >= caps[iid]
            c = len(busy) + ((1 if same_day else _BIG) if full else 0)
            cands.append((c, str(iid), iid, busy, full, same_day))
        cands.sort(key=lambda t: t[:2])
        for c, _, iid, busy, full, same_day in cands[: r.stage.panel_size]:
            if busy:
                blockers.append(Blocker(BlockerKind.INTERVIEWER_BUSY, iid, tuple(busy)))
            if full:
                blockers.append(Blocker(BlockerKind.INTERVIEWER_DAILY_CAPACITY, iid,
                                        tuple(same_day)))
            cost += c

        if best is None or (cost, x) < (best[0], best[1]):
            best = (cost, x, blockers)
    return (best[1], tuple(best[2])) if best else (None, ())


# ------------------------------------------------------------------ what-ifs


def _what_ifs(inp, result, prep, reqs, left, budget, time_limit):
    cfg = replace(inp.config, time_limit_seconds=time_limit)
    base = len(result.interviews)
    horizon = (Window(inp.config.horizon_start, inp.config.horizon_end),)
    left_reqs = [reqs[k] for k in left]
    tests: list[tuple[FixKind, str, Id | None, ScheduleInput]] = []

    def variant(**changes) -> ScheduleInput:
        return replace(inp, config=cfg, **changes)

    # 1. one more room, big enough for the largest unscheduled panel
    seats = max(r.stage.panel_size + 1 for r in left_reqs)
    rid = ("__added__", "room")
    tests.append((FixKind.ADD_ROOM, f"add one more room seating {seats}", None,
                  variant(rooms=inp.rooms + (RoomSpec(rid, max(seats, 2), "added room"),))))

    # 2. one more interviewer per distinct skill set that was needed
    for n, skills in enumerate(sorted({r.stage.required_skills for r in left_reqs}, key=sorted)):
        label = ", ".join(sorted(skills)) or "no special skills"
        iid = ("__added__", "interviewer", n)
        extra = InterviewerSpec(iid, frozenset(skills), horizon, len(left_reqs) + 8)
        tests.append((FixKind.ADD_INTERVIEWER,
                      f"add one more interviewer free all drive long with: {label}", None,
                      variant(interviewers=inp.interviewers + (extra,))))

    # 3. +1 daily capacity for qualified interviewers who hit their limit
    day_counts: dict[tuple[Id, int], int] = dict(prep.used_per_day)
    for p in _proposed_info(prep, result):
        if p.day is not None:
            for iid in p.iv.interviewer_ids:
                day_counts[(iid, p.day)] = day_counts.get((iid, p.day), 0) + 1
    qualified = {
        i.id for i in inp.interviewers
        for r in left_reqs
        if {s.lower() for s in r.stage.required_skills} <= {s.lower() for s in i.skills}
    }
    for i in inp.interviewers:
        if i.id in qualified and any(
            iid == i.id and n >= i.capacity_per_day for (iid, _), n in day_counts.items()
        ):
            bumped = tuple(replace(x, capacity_per_day=x.capacity_per_day + 1) if x.id == i.id
                           else x for x in inp.interviewers)
            tests.append((FixKind.RAISE_DAILY_CAPACITY,
                          f"let interviewer {i.id!r} take one more interview per day "
                          f"(now {i.capacity_per_day})", i.id, variant(interviewers=bumped)))

    # 4. candidates free for the whole drive window
    for cid in dict.fromkeys(r.candidate.id for r in left_reqs):
        widened = tuple(replace(c, availability=horizon) if c.id == cid else c
                        for c in inp.candidates)
        tests.append((FixKind.WIDEN_CANDIDATE_AVAILABILITY,
                      f"ask candidate {cid!r} for more availability", cid,
                      variant(candidates=widened)))

    # 5. qualified interviewers free for the whole drive window
    for i in inp.interviewers:
        if i.id in qualified and i.availability != horizon:
            widened = tuple(replace(x, availability=horizon) if x.id == i.id else x
                            for x in inp.interviewers)
            tests.append((FixKind.WIDEN_INTERVIEWER_AVAILABILITY,
                          f"ask interviewer {i.id!r} for more availability", i.id,
                          variant(interviewers=widened)))

    exhausted = len(tests) > budget
    out: list[WhatIf] = []
    wanted = set(left)
    for kind, text, target, variant_inp in tests[:budget]:
        res = solve(variant_inp)
        got = {(iv.candidate_id, iv.stage_id) for iv in res.interviews}
        out.append(WhatIf(kind, text, target, len(res.interviews),
                          tuple(sorted(wanted & got, key=str)) if len(res.interviews) >= base
                          else ()))
    return out, exhausted


# ------------------------------------------------------------------ wording


def _fmt(prep: Prepared, tz, dt: datetime) -> str:
    return dt.astimezone(tz).strftime("%a %H:%M")


def _summary(u, codes, slot, blockers, fixes, prep, tz, caps) -> str:
    if ReasonCode.CAPACITY_CONTENTION not in codes:
        text = "; ".join(r.detail for r in u.reasons)
    elif slot is None or not blockers:
        text = ("It fits on its own, but every free slot depends on how its other rounds "
                "are arranged.")
    else:
        parts = []
        for b in blockers:
            who = ", ".join(
                f"candidate {iv.candidate_id!r} {_fmt(prep, tz, iv.start)}-"
                f"{iv.end.astimezone(tz).strftime('%H:%M')}" for iv in b.interviews[:3]
            ) or "existing bookings"
            if b.kind is BlockerKind.ROOM_BUSY:
                parts.append(f"room {b.resource_id!r} is in use ({who})")
            elif b.kind is BlockerKind.INTERVIEWER_BUSY:
                parts.append(f"interviewer {b.resource_id!r} is already in a session ({who})")
            else:
                parts.append(f"interviewer {b.resource_id!r} is at their daily limit of "
                             f"{caps[b.resource_id]} ({who})")
        text = (f"The best slot would be {_fmt(prep, tz, prep.slot_to_dt(slot))}, but "
                + "; ".join(parts) + ".")
    if fixes:
        text += " Would be fixed by: " + "; or ".join(f.description for f in fixes[:3]) + "."
    return text
