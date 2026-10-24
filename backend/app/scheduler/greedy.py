"""Fast first-fit schedule, used as a starting hint for CP-SAT.

CP-SAT is strong at improving a good schedule but can be slow to find its first
one on big drives. This builds a valid schedule greedily (most constrained
requests first, earliest start, lightest-loaded interviewers, smallest room)
and the solver starts from it. The result is only a hint: the solver may change
anything, and correctness never depends on it.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.scheduler.prepare import Prepared, Request
from app.scheduler.types import Anchor, Id


@dataclass
class Placement:
    start: int
    room: Id
    panel: tuple[Id, ...]


def _in(spans, x: int) -> bool:
    return any(a <= x < b for a, b in spans)


def _free(busy: list[tuple[int, int]], s: int, e: int) -> bool:
    return all(e <= bs or be <= s for bs, be in busy)


def greedy_plan(
    prep: Prepared,
    room_cap: dict[Id, int],
    intv_cap: dict[Id, int],
    anchors: dict[tuple[Id, Id], Anchor] | None = None,
) -> dict[int, Placement]:
    anchors = anchors or {}
    buf, gap = prep.buffer_slots, prep.gap_slots
    room_busy: dict[Id, list[tuple[int, int]]] = {}
    intv_busy: dict[Id, list[tuple[int, int]]] = {}
    day_count: dict[tuple[Id, int], int] = dict(prep.used_per_day)
    load: dict[Id, int] = dict(prep.existing_load)
    placed: dict[int, Placement] = {}

    def try_at(r: Request, x: int, want_room=None, want_panel=None) -> Placement | None:
        d = r.duration_slots
        rooms = [rid for rid, sp in r.room_starts.items()
                 if _in(sp, x) and _free(room_busy.get(rid, []), x, x + d)]
        if not rooms:
            return None
        day = prep.day_of[x]
        ok = [iid for iid, sp in r.interviewer_starts.items()
              if _in(sp, x) and _free(intv_busy.get(iid, []), x, x + d + buf)
              and day_count.get((iid, day), 0) < _cap(iid)]
        if len(ok) < r.stage.panel_size:
            return None
        room = want_room if want_room in rooms else min(rooms, key=lambda k: (room_cap[k], str(k)))
        if want_panel and all(i in ok for i in want_panel):
            panel = tuple(want_panel)
        else:
            panel = tuple(sorted(ok, key=lambda k: (load.get(k, 0), str(k)))[: r.stage.panel_size])
        return Placement(x, room, panel)

    def _cap(iid: Id) -> int:
        return intv_cap[iid]

    def commit(r: Request, p: Placement) -> None:
        d = r.duration_slots
        room_busy.setdefault(p.room, []).append((p.start, p.start + d))
        for iid in p.panel:
            intv_busy.setdefault(iid, []).append((p.start, p.start + d + buf))
            key = (iid, prep.day_of[p.start])
            day_count[key] = day_count.get(key, 0) + 1
            load[iid] = load.get(iid, 0) + 1
        placed[r.index] = p

    active = [r for r in prep.requests if not r.reasons]
    groups: dict[Id, list[Request]] = {}
    for r in active:
        groups.setdefault(r.candidate.id, []).append(r)
    ordered = sorted(groups.values(),
                     key=lambda g: (min(sum(b - a for a, b in r.starts) for r in g), g[0].index))

    def lower_bound(r: Request) -> int | None:
        """Earliest start allowed by this candidate's earlier round, if placed."""
        if r.prev is None:
            return 0
        if r.prev not in placed:
            return None
        return placed[r.prev].start + prep.requests[r.prev].duration_slots + gap

    # Pass 1: put every anchored interview back exactly where it was, if it still fits.
    # Doing this before anything else stops displaced interviews taking others' slots.
    if anchors:
        for group in ordered:
            for r in sorted(group, key=lambda r: r.stage.order_index):
                a = anchors.get((r.candidate.id, r.stage.id))
                lo = lower_bound(r)
                if a is None or lo is None:
                    continue
                x = prep.floor_slot(a.start)
                if x >= lo and _in(r.starts, x):
                    res = try_at(r, x, a.room_id, a.interviewer_ids)
                    if res and res.room == a.room_id and set(res.panel) == set(a.interviewer_ids):
                        commit(r, res)

    # Pass 2: everything else, earliest fit.
    for group in ordered:
        for r in sorted(group, key=lambda r: r.stage.order_index):
            if r.index in placed:
                continue
            lo = lower_bound(r)
            if lo is None:
                continue
            result = None
            for s_, e_ in r.starts:
                for x in range(max(s_, lo), e_):
                    result = try_at(r, x)
                    if result:
                        break
                if result:
                    break
            if result:
                commit(r, result)
    return placed
