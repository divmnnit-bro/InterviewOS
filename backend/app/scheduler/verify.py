"""Independent checker for a proposed schedule.

Works on datetimes directly and shares no code with the solver, so a bug in
the model cannot hide itself here. The service layer should call `verify`
before saving a proposal ("the solver proposes, the backend checks").
Returns a list of human-readable violations; empty means the schedule is valid.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.scheduler.types import Id, ScheduleInput, ScheduleResult, Window


def _merged(windows) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    for s, e in sorted((w.start, w.end) for w in windows):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _contained(windows, s: datetime, e: datetime) -> bool:
    return any(ws <= s and e <= we for ws, we in _merged(windows))


def verify(inp: ScheduleInput, result: ScheduleResult) -> list[str]:
    cfg = inp.config
    stages = {s.id: s for s in inp.stages}
    cands = {c.id: c for c in inp.candidates}
    intvs = {i.id: i for i in inp.interviewers}
    rooms = {r.id: r for r in inp.rooms}
    buf = timedelta(minutes=cfg.interviewer_buffer_minutes)
    gap = timedelta(minutes=cfg.min_round_gap_minutes)
    bad: list[str] = []

    seen: set[tuple[Id, Id]] = set()
    for iv in result.interviews:
        tag = f"interview(cand={iv.candidate_id!r}, stage={iv.stage_id!r})"
        st, cand = stages.get(iv.stage_id), cands.get(iv.candidate_id)
        if st is None or cand is None:
            bad.append(f"{tag}: unknown candidate or stage")
            continue
        if iv.stage_id not in cand.stage_ids:
            bad.append(f"{tag}: stage was not requested for this candidate")
        if (iv.candidate_id, iv.stage_id) in seen:
            bad.append(f"{tag}: scheduled twice")
        seen.add((iv.candidate_id, iv.stage_id))

        if iv.end - iv.start != timedelta(minutes=st.duration_minutes):
            bad.append(f"{tag}: wrong duration")
        if iv.start < cfg.horizon_start or iv.end > cfg.horizon_end:
            bad.append(f"{tag}: outside the drive window")
        if not _contained(cand.availability, iv.start, iv.end):
            bad.append(f"{tag}: candidate not available")
        if cand.not_before and iv.start < cand.not_before and \
                min(stages[s].order_index for s in cand.stage_ids) == st.order_index:
            bad.append(f"{tag}: starts before not_before")

        if len(iv.interviewer_ids) != len(set(iv.interviewer_ids)):
            bad.append(f"{tag}: interviewer listed twice")
        if len(iv.interviewer_ids) != st.panel_size:
            bad.append(f"{tag}: panel has {len(iv.interviewer_ids)}, needs {st.panel_size}")
        need = {s.lower() for s in st.required_skills}
        for iid in iv.interviewer_ids:
            i = intvs.get(iid)
            if i is None:
                bad.append(f"{tag}: unknown interviewer {iid!r}")
                continue
            if not need <= {s.lower() for s in i.skills}:
                bad.append(f"{tag}: interviewer {iid!r} lacks required skills")
            if not _contained(i.availability, iv.start, iv.end):
                bad.append(f"{tag}: interviewer {iid!r} not available")
        room = rooms.get(iv.room_id)
        if room is None:
            bad.append(f"{tag}: unknown room")
        else:
            if room.capacity < st.panel_size + 1:
                bad.append(f"{tag}: room {iv.room_id!r} too small")
            if room.availability is not None and not _contained(room.availability, iv.start, iv.end):
                bad.append(f"{tag}: room {iv.room_id!r} not available")

    # round order and gap
    by_cand: dict[Id, list] = {}
    for iv in result.interviews:
        if iv.stage_id in stages:
            by_cand.setdefault(iv.candidate_id, []).append(iv)
    for cid, ivs in by_cand.items():
        ivs.sort(key=lambda x: stages[x.stage_id].order_index)
        for a, b in zip(ivs, ivs[1:]):
            if b.start < a.end + gap:
                bad.append(f"candidate {cid!r}: round order or gap violated")
        requested = sorted(stages[s].order_index for s in cands[cid].stage_ids)
        got = [stages[x.stage_id].order_index for x in ivs]
        if got != requested[: len(got)]:
            bad.append(f"candidate {cid!r}: scheduled a round without its earlier rounds")

    # overlaps, including against existing bookings
    def busy(kind: str):
        out: dict[Id, list[tuple[datetime, datetime, str]]] = {}
        for iv in result.interviews:
            keys = {"cand": [iv.candidate_id], "room": [iv.room_id],
                    "intv": list(iv.interviewer_ids)}[kind]
            pad = buf if kind == "intv" else timedelta(0)
            for k in keys:
                out.setdefault(k, []).append((iv.start, iv.end + pad, "new"))
        for b in inp.existing:
            keys = {"cand": [b.candidate_id], "room": [b.room_id],
                    "intv": list(b.interviewer_ids)}[kind]
            pad = buf if kind == "intv" else timedelta(0)
            for k in keys:
                if k is not None:
                    out.setdefault(k, []).append((b.start - pad, b.end + pad, "old"))
        return out

    for kind, label in (("cand", "candidate"), ("room", "room"), ("intv", "interviewer")):
        for k, spans in busy(kind).items():
            spans.sort()
            for (s1, e1, t1), (s2, e2, t2) in zip(spans, spans[1:]):
                if s2 < e1 and not (t1 == "old" and t2 == "old"):
                    bad.append(f"{label} {k!r} double booked ({t1} vs {t2})")

    # daily capacity, counted on the local day a session starts
    counts: dict[tuple[Id, object], int] = {}
    tz = cfg.tz
    starts = [(iid, iv.start) for iv in result.interviews for iid in iv.interviewer_ids]
    starts += [(iid, b.start) for b in inp.existing for iid in b.interviewer_ids
               if cfg.horizon_start <= b.start < cfg.horizon_end]
    for iid, s in starts:
        key = (iid, s.astimezone(tz).date())
        counts[key] = counts.get(key, 0) + 1
    for (iid, day), n in counts.items():
        if iid in intvs and n > intvs[iid].capacity_per_day:
            bad.append(f"interviewer {iid!r} has {n} sessions on {day}, "
                       f"capacity {intvs[iid].capacity_per_day}")
    return bad
