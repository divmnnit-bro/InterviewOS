"""CP-SAT model: builds and solves one scheduling run.

Hard constraints
  * each interview sits entirely inside the candidate's free time
  * panel members are qualified (all required skills) and free for the whole slot
  * the room seats panel + candidate and is free for the whole slot
  * no interviewer, room or candidate is double booked (existing bookings included)
  * an interviewer rests `interviewer_buffer_minutes` between sessions
  * an interviewer takes at most `capacity_per_day` interviews per local day
  * a candidate's rounds run in order, `min_round_gap_minutes` apart

Soft preferences (weights in `Weights`)
  * schedule as many interviews as possible (always dominates the rest)
  * earlier is better
  * spread work evenly (minimise the busiest interviewer's load)
  * use the smallest adequate room

If not every request can be placed the run still returns the best partial
schedule, plus a reason for each request left out.
"""
from __future__ import annotations

import time
from datetime import timedelta

from ortools.sat.python import cp_model

from app.scheduler.greedy import greedy_plan
from app.scheduler.prepare import Prepared, Request, prepare
from app.scheduler.types import (
    Anchor,
    DisruptionWeights,
    Id,
    ProposedInterview,
    Reason,
    ReasonCode,
    ScheduleInput,
    ScheduleResult,
    SolveStatus,
    Unscheduled,
)
from app.scheduler.validation import validate_input


def _domain(spans) -> cp_model.Domain:
    return cp_model.Domain.from_intervals([[s, e - 1] for s, e in spans])


def solve(
    inp: ScheduleInput,
    anchors: dict[tuple[Id, Id], Anchor] | None = None,
    disruption: DisruptionWeights | None = None,
) -> ScheduleResult:
    """Solve one run.

    `anchors` maps (candidate_id, stage_id) to a current placement. Anchored
    interviews are not pulled earlier or toward small rooms; instead every
    change from the anchor costs `disruption` points (see DisruptionWeights).
    """
    anchors = anchors or {}
    dw = disruption or DisruptionWeights()
    validate_input(inp)
    prep = prepare(inp)
    reqs = prep.requests
    if not reqs:
        return ScheduleResult(SolveStatus.NOTHING_TO_SCHEDULE, (), ())

    cfg = inp.config
    wts = cfg.weights
    room_cap = {r.id: r.capacity for r in inp.rooms}
    intv_cap = {i.id: i.capacity_per_day for i in inp.interviewers}
    active = [r for r in reqs if not r.reasons]

    m = cp_model.CpModel()
    sched = {r.index: m.new_bool_var(f"sched_{r.index}") for r in reqs}
    start: dict[int, cp_model.IntVar] = {}
    for r in reqs:
        if r.reasons:
            m.add(sched[r.index] == 0)
        else:
            start[r.index] = m.new_int_var_from_domain(_domain(r.starts), f"start_{r.index}")

    # ---- interviewers: choose panel, forbid overlap (with rest buffer)
    assign: dict[tuple[int, Id], cp_model.IntVar] = {}
    intv_ivs: dict[Id, list] = {}
    for r in active:
        lits = []
        for iid, spans in r.interviewer_starts.items():
            lit = m.new_bool_var(f"a_{r.index}_{iid}")
            assign[(r.index, iid)] = lit
            lits.append(lit)
            if spans != r.starts:
                m.add_linear_expression_in_domain(start[r.index], _domain(spans)).only_enforce_if(lit)
            iv = m.new_optional_fixed_size_interval_var(
                start[r.index], r.duration_slots + prep.buffer_slots, lit, f"ia_{r.index}_{iid}"
            )
            intv_ivs.setdefault(iid, []).append(iv)
        m.add(sum(lits) == r.stage.panel_size).only_enforce_if(sched[r.index])
        m.add(sum(lits) == 0).only_enforce_if(sched[r.index].Not())
    for ivs in intv_ivs.values():
        if len(ivs) > 1:
            m.add_no_overlap(ivs)

    # ---- rooms: exactly one, big enough, no overlap
    room_lit: dict[tuple[int, Id], cp_model.IntVar] = {}
    room_ivs: dict[Id, list] = {}
    for r in active:
        lits = []
        for rid, spans in r.room_starts.items():
            lit = m.new_bool_var(f"r_{r.index}_{rid}")
            room_lit[(r.index, rid)] = lit
            lits.append(lit)
            if spans != r.starts:
                m.add_linear_expression_in_domain(start[r.index], _domain(spans)).only_enforce_if(lit)
            room_ivs.setdefault(rid, []).append(
                m.new_optional_fixed_size_interval_var(
                    start[r.index], r.duration_slots, lit, f"ra_{r.index}_{rid}"
                )
            )
        m.add(sum(lits) == sched[r.index])
    for ivs in room_ivs.values():
        if len(ivs) > 1:
            m.add_no_overlap(ivs)

    # ---- a candidate's rounds in order
    for r in active:
        if r.prev is None:
            continue
        p = reqs[r.prev]
        m.add_implication(sched[r.index], sched[p.index])
        m.add(
            start[r.index] >= start[p.index] + p.duration_slots + prep.gap_slots
        ).only_enforce_if(sched[r.index])

    # ---- daily interviewer capacity (only built where it can actually bind)
    day_lits, both_lits = _add_daily_capacity(m, prep, active, sched, start, assign, intv_cap)

    # ---- objective
    loads: dict[Id, list] = {}
    for (ri, iid), lit in assign.items():
        loads.setdefault(iid, []).append(lit)
    max_load = None
    if wts.load_balance and len(loads) > 1:
        ceiling = len(active) + max(prep.existing_load.values(), default=0)
        max_load = m.new_int_var(0, ceiling, "max_load")
        for iid, lits in loads.items():
            m.add(max_load >= sum(lits) + prep.existing_load.get(iid, 0))

    anchored = {r.index for r in active if (r.candidate.id, r.stage.id) in anchors}
    soft = []
    if wts.earliness:
        soft += [wts.earliness * start[r.index] for r in active if r.index not in anchored]
    if max_load is not None:
        soft.append(wts.load_balance * max_load)
    if wts.room_fit:
        for (ri, rid), lit in room_lit.items():
            if ri in anchored:
                continue
            spare = room_cap[rid] - (reqs[ri].stage.panel_size + 1)
            if spare:
                soft.append(wts.room_fit * spare * lit)

    anchor_vars: dict[int, tuple] = {}
    disruption_bound = 0
    for r in active:
        a = anchors.get((r.candidate.id, r.stage.id))
        if a is None:
            continue
        a_slot = prep.floor_slot(a.start)
        kept = m.new_bool_var(f"kept_{r.index}")
        m.add_implication(kept, sched[r.index])
        m.add(start[r.index] == a_slot).only_enforce_if(kept)
        soft.append(dw.time_change * (1 - kept))
        diff = m.new_int_var(0, prep.n_slots, f"shift_{r.index}")
        m.add_abs_equality(diff, start[r.index] - a_slot)
        soft.append(dw.shift_per_slot * diff)
        anchor_vars[r.index] = (kept, diff, a_slot)
        rl = room_lit.get((r.index, a.room_id))
        soft.append(dw.room_change if rl is None else dw.room_change * (1 - rl))
        for iid in a.interviewer_ids:
            al = assign.get((r.index, iid))
            soft.append(dw.panel_change if al is None else dw.panel_change * (1 - al))
        disruption_bound += (dw.time_change + dw.shift_per_slot * prep.n_slots
                             + dw.room_change + dw.panel_change * len(a.interviewer_ids))

    # Scheduling must beat any possible soft saving, whatever the weights say.
    soft_bound = (
        disruption_bound +
        wts.earliness * prep.n_slots * len(active)
        + wts.load_balance * (len(active) + max(prep.existing_load.values(), default=0))
        + wts.room_fit * max(room_cap.values(), default=0) * len(active)
        + 1
    )
    w_sched = max(wts.scheduled, soft_bound)
    m.minimize(sum(soft) - w_sched * sum(sched.values()))

    # Start from a quick greedy schedule so big drives get a good answer fast.
    # Every variable is hinted, helper variables included, so the solver can
    # take the greedy schedule over whole instead of having to repair it.
    plan = greedy_plan(prep, room_cap, intv_cap, anchors)
    assign_by_r: dict[int, list] = {}
    for (ri, iid), lit in assign.items():
        assign_by_r.setdefault(ri, []).append((iid, lit))
    room_by_r: dict[int, list] = {}
    for (ri, rid), lit in room_lit.items():
        room_by_r.setdefault(ri, []).append((rid, lit))
    hint_start: dict[int, int] = {}
    hint_assign: dict[tuple[int, Id], int] = {}
    for r in active:
        p = plan.get(r.index)
        m.add_hint(sched[r.index], 1 if p else 0)
        if p:
            x = p.start
        elif r.index in anchor_vars and any(a <= anchor_vars[r.index][2] < b for a, b in r.starts):
            x = anchor_vars[r.index][2]
        else:
            x = r.starts[0][0]
        hint_start[r.index] = x
        m.add_hint(start[r.index], x)
        for iid, lit in assign_by_r.get(r.index, []):
            v = 1 if p and iid in p.panel else 0
            hint_assign[(r.index, iid)] = v
            m.add_hint(lit, v)
        for rid, lit in room_by_r.get(r.index, []):
            m.add_hint(lit, 1 if p and rid == p.room else 0)
        if r.index in anchor_vars:
            kept, diff, a_slot = anchor_vars[r.index]
            m.add_hint(kept, 1 if p and p.start == a_slot else 0)
            m.add_hint(diff, abs(x - a_slot))
    for ri, dmap in day_lits.items():
        p = plan.get(ri)
        for d, lit in dmap.items():
            m.add_hint(lit, 1 if p and prep.day_of[p.start] == d else 0)
    for (ri, iid, d), lit in both_lits.items():
        p = plan.get(ri)
        m.add_hint(lit, 1 if p and iid in p.panel and prep.day_of[p.start] == d else 0)
    if max_load is not None:
        counts: dict[Id, int] = dict(prep.existing_load)
        for p in plan.values():
            for iid in p.panel:
                counts[iid] = counts.get(iid, 0) + 1
        m.add_hint(max_load, max(counts.values(), default=0))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg.time_limit_seconds
    solver.parameters.num_workers = cfg.workers
    solver.parameters.random_seed = cfg.seed
    # Symmetry detection and probing can use up the whole time budget on big drives
    # before search even starts, so both are switched off.
    solver.parameters.symmetry_level = 0
    solver.parameters.cp_model_probing_level = 0
    t0 = time.perf_counter()
    status = solver.solve(m)
    elapsed = time.perf_counter() - t0

    if status == cp_model.MODEL_INVALID:
        raise RuntimeError(f"scheduler built an invalid model: {m.validate()}")
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Leaving everything unscheduled is always valid, so this means the time
        # limit hit before any solution was found. Fall back to the greedy plan.
        return _fallback(prep, reqs, plan, elapsed)

    interviews: list[ProposedInterview] = []
    left: list[Unscheduled] = []
    placed: set[int] = set()
    load: dict[Id, int] = {}
    for r in reqs:
        if r.index in start and solver.value(sched[r.index]):
            placed.add(r.index)
            s = solver.value(start[r.index])
            room = next(rid for (ri, rid), lit in room_lit.items()
                        if ri == r.index and solver.value(lit))
            panel = tuple(iid for (ri, iid), lit in assign.items()
                          if ri == r.index and solver.value(lit))
            for iid in panel:
                load[iid] = load.get(iid, 0) + 1
            begin = prep.slot_to_dt(s)
            interviews.append(ProposedInterview(
                r.candidate.id, r.stage.id, begin,
                begin + timedelta(minutes=r.stage.duration_minutes), room, panel,
            ))
    for r in reqs:
        if r.index in placed:
            continue
        if r.reasons:
            reasons = tuple(r.reasons)
        elif r.prev is not None and r.prev not in placed:
            reasons = (Reason(ReasonCode.PREVIOUS_ROUND_UNSCHEDULED,
                              "the candidate's earlier round could not be scheduled"),)
        else:
            reasons = (Reason(
                ReasonCode.CAPACITY_CONTENTION,
                "fits on its own, but every possible slot is taken by other interviews "
                "or hits an interviewer's daily capacity",
            ),)
        left.append(Unscheduled(r.candidate.id, r.stage.id, reasons))

    interviews.sort(key=lambda x: (x.start, str(x.candidate_id)))
    return ScheduleResult(
        SolveStatus.OPTIMAL if status == cp_model.OPTIMAL else SolveStatus.FEASIBLE,
        tuple(interviews), tuple(left),
        objective=int(solver.objective_value),
        wall_time_seconds=elapsed,
        load_per_interviewer=load,
    )


def _fallback(prep: Prepared, reqs: list[Request], plan, elapsed: float) -> ScheduleResult:
    interviews, left = [], []
    for r in reqs:
        p = plan.get(r.index)
        if p is None:
            reasons = tuple(r.reasons) or (Reason(
                ReasonCode.SOLVER_TIMEOUT,
                "could not be placed by the quick scheduler and the full solver ran out of time"),)
            left.append(Unscheduled(r.candidate.id, r.stage.id, reasons))
            continue
        begin = prep.slot_to_dt(p.start)
        interviews.append(ProposedInterview(
            r.candidate.id, r.stage.id, begin,
            begin + timedelta(minutes=r.stage.duration_minutes), p.room, p.panel))
    load: dict[Id, int] = {}
    for iv in interviews:
        for iid in iv.interviewer_ids:
            load[iid] = load.get(iid, 0) + 1
    interviews.sort(key=lambda x: (x.start, str(x.candidate_id)))
    status = SolveStatus.HEURISTIC if interviews else SolveStatus.UNKNOWN
    return ScheduleResult(status, tuple(interviews), tuple(left),
                          wall_time_seconds=elapsed, load_per_interviewer=load)


def _add_daily_capacity(m, prep: Prepared, active: list[Request], sched, start, assign, intv_cap):
    """sum over a day of an interviewer's sessions <= capacity - already booked.

    A session counts on the local day it starts. Terms are only created for
    (interviewer, day) pairs where demand could exceed what is left.
    """
    days_of = {
        r.index: sorted({prep.day_of[x] for s, e in r.starts for x in range(s, e)})
        for r in active
    }
    demand: dict[tuple[Id, int], int] = {}
    for r in active:
        for iid in r.interviewer_starts:
            for d in days_of[r.index]:
                demand[(iid, d)] = demand.get((iid, d), 0) + 1

    day_lits: dict[int, dict[int, cp_model.IntVar]] = {}

    def lits_for(r: Request) -> dict[int, cp_model.IntVar]:
        if r.index not in day_lits:
            lits = {}
            for d in days_of[r.index]:
                lit = m.new_bool_var(f"day_{r.index}_{d}")
                spans = [(x, x + 1) for s, e in r.starts for x in range(s, e)
                         if prep.day_of[x] == d]
                m.add_linear_expression_in_domain(
                    start[r.index], _domain(_merge(spans))
                ).only_enforce_if(lit)
                lits[d] = lit
            m.add(sum(lits.values()) == sched[r.index])
            day_lits[r.index] = lits
        return day_lits[r.index]

    terms: dict[tuple[Id, int], list] = {}
    both_vars: dict[tuple[int, Id, int], cp_model.IntVar] = {}
    for (iid, d), n_demand in demand.items():
        left = intv_cap[iid] - prep.used_per_day.get((iid, d), 0)
        if n_demand <= left:
            continue
        terms[(iid, d)] = []
    for r in active:
        for iid in r.interviewer_starts:
            a = assign[(r.index, iid)]
            for d in days_of[r.index]:
                if (iid, d) not in terms:
                    continue
                if len(days_of[r.index]) == 1:
                    terms[(iid, d)].append(a)   # assigned implies scheduled implies this day
                else:
                    both = m.new_bool_var(f"cap_{r.index}_{iid}_{d}")
                    dl = lits_for(r)[d]
                    m.add_bool_and([a, dl]).only_enforce_if(both)
                    m.add_bool_or([a.Not(), dl.Not(), both])
                    terms[(iid, d)].append(both)
                    both_vars[(r.index, iid, d)] = both
    for (iid, d), lits in terms.items():
        left = intv_cap[iid] - prep.used_per_day.get((iid, d), 0)
        m.add(sum(lits) <= max(left, 0))
    return day_lits, both_vars


def _merge(spans):
    from app.scheduler.windows import merge
    return merge(spans)
