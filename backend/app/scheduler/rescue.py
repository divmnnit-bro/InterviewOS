"""Ripple Rescue: repair a published schedule after something breaks.

Given the interviews as they stand and one or more disruptions (an interviewer
falls ill, a room is closed, a candidate cannot attend), find the repair that
disturbs the fewest people:

  1. keep as many interviews scheduled as possible (never drop one just to
     avoid moving another),
  2. then change as little as possible. Changing a time or room reaches the
     candidate; swapping a panel member is internal and cheap. Small time
     shifts beat big ones.

An interview that is not directly hit may still move if that is the only way
to fit an affected one in. Those are reported as collateral, so the
coordinator can see the ripple. Interviews already started or marked `locked`
never move.

Pure logic: nothing is saved. The caller applies the plan and sends notices.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum

from app.scheduler.solver import solve
from app.scheduler.types import (
    Anchor,
    DisruptionWeights,
    ExistingBooking,
    Id,
    InterviewerSpec,
    ProposedInterview,
    Reason,
    RoomSpec,
    ScheduleInput,
    SolveStatus,
    Weights,
    Window,
)
from app.scheduler.validation import InvalidScheduleInput, validate_input
from app.scheduler.verify import verify


class DisruptionKind(str, Enum):
    INTERVIEWER_OUT = "interviewer_out"
    ROOM_OUT = "room_out"
    CANDIDATE_OUT = "candidate_out"


class Change(str, Enum):
    TIME = "time"
    ROOM = "room"
    PANEL = "panel"


@dataclass(frozen=True)
class Disruption:
    kind: DisruptionKind
    resource_id: Id
    start: datetime
    end: datetime


@dataclass(frozen=True)
class CurrentInterview:
    id: Id                      # the saved interview's id, echoed back in the plan
    candidate_id: Id
    stage_id: Id
    start: datetime
    end: datetime
    room_id: Id
    interviewer_ids: tuple[Id, ...]
    locked: bool = False


@dataclass(frozen=True)
class Placement:
    start: datetime
    end: datetime
    room_id: Id
    interviewer_ids: tuple[Id, ...]


@dataclass(frozen=True)
class Move:
    interview_id: Id
    candidate_id: Id
    stage_id: Id
    old: Placement
    new: Placement
    changes: frozenset[Change]
    directly_affected: bool

    @property
    def notifies_candidate(self) -> bool:
        return bool(self.changes & {Change.TIME, Change.ROOM})


@dataclass(frozen=True)
class Dropped:
    interview_id: Id
    candidate_id: Id
    stage_id: Id
    reasons: tuple[Reason, ...]


@dataclass(frozen=True)
class RescuePlan:
    status: SolveStatus
    moves: tuple[Move, ...]
    dropped: tuple[Dropped, ...]
    needs_manual: tuple[Id, ...]        # locked interviews that a disruption hits
    unchanged: tuple[Id, ...]
    affected: tuple[Id, ...]            # interviews directly hit by a disruption
    candidates_to_notify: tuple[Id, ...]
    interviewers_to_notify: tuple[Id, ...]
    new_schedule: tuple[ProposedInterview, ...]   # every re-placed interview, after repair
    violations: tuple[str, ...]         # from the independent checker; should be empty

    @property
    def collateral(self) -> tuple[Move, ...]:
        return tuple(m for m in self.moves if not m.directly_affected)

    @property
    def fully_repaired(self) -> bool:
        return not self.dropped and not self.needs_manual


def _cut(windows: tuple[Window, ...], out_s: datetime, out_e: datetime) -> tuple[Window, ...]:
    res: list[Window] = []
    for w in windows:
        if w.end <= out_s or w.start >= out_e:
            res.append(w)
            continue
        if w.start < out_s:
            res.append(Window(w.start, out_s))
        if out_e < w.end:
            res.append(Window(out_e, w.end))
    return tuple(res)


def _overlaps(s1: datetime, e1: datetime, s2: datetime, e2: datetime) -> bool:
    return s1 < e2 and s2 < e1


def rescue(
    inp: ScheduleInput,
    current: list[CurrentInterview] | tuple[CurrentInterview, ...],
    disruptions: list[Disruption] | tuple[Disruption, ...],
    *,
    now: datetime | None = None,
    disruption_weights: DisruptionWeights | None = None,
) -> RescuePlan:
    """Repair `current` after `disruptions`.

    `inp` describes the drive as usual (stages, candidates, interviewers, rooms,
    config). `inp.existing` must hold only bookings that are NOT in `current`.
    Candidates with no current interview are ignored. If `now` is given,
    interviews that start before it are locked and nothing is moved earlier
    than it.
    """
    validate_input(inp)
    cfg = inp.config
    stage_by_id = {s.id: s for s in inp.stages}
    cand_by_id = {c.id: c for c in inp.candidates}
    room_ids = {r.id for r in inp.rooms}
    intv_ids = {i.id for i in inp.interviewers}

    # ---- check the description of the current schedule
    problems: list[str] = []
    seen_ids: set[Id] = set()
    seen_keys: set[tuple[Id, Id]] = set()
    for c in current:
        tag = f"current interview {c.id!r}"
        if c.id in seen_ids:
            problems.append(f"{tag}: duplicate id")
        seen_ids.add(c.id)
        if (c.candidate_id, c.stage_id) in seen_keys:
            problems.append(f"{tag}: candidate already has this stage")
        seen_keys.add((c.candidate_id, c.stage_id))
        if c.stage_id not in stage_by_id or c.candidate_id not in cand_by_id:
            problems.append(f"{tag}: unknown stage or candidate")
            continue
        if c.room_id not in room_ids or not set(c.interviewer_ids) <= intv_ids:
            problems.append(f"{tag}: unknown room or interviewer")
        if c.end - c.start != _minutes(stage_by_id[c.stage_id].duration_minutes):
            problems.append(f"{tag}: length does not match the stage duration")
        if c.start.tzinfo is None or c.end.tzinfo is None:
            problems.append(f"{tag}: naive datetime")
        elif not c.locked and (
            (c.start - cfg.horizon_start).total_seconds() % (cfg.slot_minutes * 60)
            or c.start < cfg.horizon_start or c.end > cfg.horizon_end
        ):
            problems.append(f"{tag}: must start on the slot grid inside the drive window")
    for d in disruptions:
        if d.end <= d.start or d.start.tzinfo is None or d.end.tzinfo is None:
            problems.append("disruption needs an aware start before its end")
    if problems:
        raise InvalidScheduleInput(problems)

    # ---- which interviews are hit
    def hit(c: CurrentInterview) -> bool:
        for d in disruptions:
            if not _overlaps(c.start, c.end, d.start, d.end):
                continue
            if (d.kind is DisruptionKind.ROOM_OUT and c.room_id == d.resource_id) or \
               (d.kind is DisruptionKind.CANDIDATE_OUT and c.candidate_id == d.resource_id) or \
               (d.kind is DisruptionKind.INTERVIEWER_OUT and d.resource_id in c.interviewer_ids):
                return True
        return False

    affected = [c for c in current if hit(c)]
    affected_ids = {c.id for c in affected}
    locked = [c for c in current if c.locked or (now is not None and c.start < now)]
    locked_ids = {c.id for c in locked}
    movable = [c for c in current if c.id not in locked_ids]
    needs_manual = tuple(c.id for c in affected if c.id in locked_ids)

    # ---- remove the broken resources from availability
    cands = {c.id: c for c in inp.candidates}
    intvs = {i.id: i for i in inp.interviewers}
    rooms = {r.id: r for r in inp.rooms}
    horizon = (Window(cfg.horizon_start, cfg.horizon_end),)
    for d in disruptions:
        if d.kind is DisruptionKind.CANDIDATE_OUT and d.resource_id in cands:
            c = cands[d.resource_id]
            cands[c.id] = replace(c, availability=_cut(c.availability, d.start, d.end))
        elif d.kind is DisruptionKind.INTERVIEWER_OUT and d.resource_id in intvs:
            i = intvs[d.resource_id]
            intvs[i.id] = replace(i, availability=_cut(i.availability, d.start, d.end))
        elif d.kind is DisruptionKind.ROOM_OUT and d.resource_id in rooms:
            r = rooms[d.resource_id]
            rooms[r.id] = replace(r, availability=_cut(r.availability or horizon, d.start, d.end))

    # ---- one request per movable interview; locked ones become fixed bookings
    by_cand: dict[Id, list[CurrentInterview]] = {}
    for c in movable:
        by_cand.setdefault(c.candidate_id, []).append(c)
    run_cands = []
    for cid, items in by_cand.items():
        base = cands[cid]
        nb = base.not_before
        if now is not None and (nb is None or nb < now):
            nb = now
        run_cands.append(replace(base, stage_ids=tuple(i.stage_id for i in items), not_before=nb))
    fixed = tuple(
        ExistingBooking(c.start, c.end, c.candidate_id, c.room_id, c.interviewer_ids)
        for c in locked
    )
    inp2 = ScheduleInput(
        stages=inp.stages,
        candidates=tuple(run_cands),
        interviewers=tuple(intvs[i.id] for i in inp.interviewers),
        rooms=tuple(rooms[r.id] for r in inp.rooms),
        config=replace(cfg, weights=Weights(
            scheduled=cfg.weights.scheduled, earliness=0, load_balance=0, room_fit=0)),
        existing=inp.existing + fixed,
    )
    anchors = {
        (c.candidate_id, c.stage_id): Anchor(c.start, c.room_id, c.interviewer_ids)
        for c in movable
    }
    result = solve(inp2, anchors, disruption_weights or DisruptionWeights())
    violations = tuple(verify(inp2, result))

    # ---- compare with what was there
    placed = {(iv.candidate_id, iv.stage_id): iv for iv in result.interviews}
    left = {(u.candidate_id, u.stage_id): u for u in result.unscheduled}
    moves: list[Move] = []
    dropped: list[Dropped] = []
    unchanged: list[Id] = []
    cand_notify: set[Id] = set()
    intv_notify: set[Id] = set()
    for c in movable:
        key = (c.candidate_id, c.stage_id)
        old = Placement(c.start, c.end, c.room_id, c.interviewer_ids)
        iv = placed.get(key)
        if iv is None:
            u = left[key]
            dropped.append(Dropped(c.id, c.candidate_id, c.stage_id, u.reasons))
            cand_notify.add(c.candidate_id)
            intv_notify.update(c.interviewer_ids)
            continue
        new = Placement(iv.start, iv.end, iv.room_id, iv.interviewer_ids)
        changes = set()
        if new.start != old.start:
            changes.add(Change.TIME)
        if new.room_id != old.room_id:
            changes.add(Change.ROOM)
        if set(new.interviewer_ids) != set(old.interviewer_ids):
            changes.add(Change.PANEL)
        if not changes:
            unchanged.append(c.id)
            continue
        mv = Move(c.id, c.candidate_id, c.stage_id, old, new, frozenset(changes),
                  c.id in affected_ids)
        moves.append(mv)
        if mv.notifies_candidate:
            cand_notify.add(c.candidate_id)
            intv_notify.update(old.interviewer_ids)
            intv_notify.update(new.interviewer_ids)
        else:
            intv_notify.update(set(old.interviewer_ids) ^ set(new.interviewer_ids))

    return RescuePlan(
        status=result.status,
        moves=tuple(moves),
        dropped=tuple(dropped),
        needs_manual=needs_manual,
        unchanged=tuple(unchanged),
        affected=tuple(c.id for c in affected),
        candidates_to_notify=tuple(sorted(cand_notify, key=str)),
        interviewers_to_notify=tuple(sorted(intv_notify, key=str)),
        new_schedule=result.interviews,
        violations=violations,
    )


def _minutes(n: int) -> timedelta:
    return timedelta(minutes=n)
