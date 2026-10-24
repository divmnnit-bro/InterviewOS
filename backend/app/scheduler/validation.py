"""Input validation. Collects every problem instead of stopping at the first."""
from __future__ import annotations

from datetime import datetime

from app.scheduler.types import ScheduleInput, Window


class InvalidScheduleInput(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("invalid scheduler input:\n- " + "\n- ".join(problems))


def _aware(dt: datetime | None) -> bool:
    return dt is None or (dt.tzinfo is not None and dt.utcoffset() is not None)


def _dupes(ids: list) -> set:
    seen: set = set()
    return {i for i in ids if i in seen or seen.add(i)}


def validate_input(inp: ScheduleInput) -> None:
    p: list[str] = []
    cfg = inp.config

    if not (_aware(cfg.horizon_start) and _aware(cfg.horizon_end)):
        p.append("horizon_start and horizon_end must be timezone-aware")
    elif cfg.horizon_end <= cfg.horizon_start:
        p.append("horizon_end must be after horizon_start")
    if cfg.slot_minutes <= 0:
        p.append("slot_minutes must be positive")
    if cfg.interviewer_buffer_minutes < 0 or cfg.min_round_gap_minutes < 0:
        p.append("buffer and gap minutes cannot be negative")
    if cfg.workers < 1 or cfg.time_limit_seconds <= 0:
        p.append("workers must be >= 1 and time_limit_seconds > 0")
    try:
        cfg.tz
    except Exception:  # ZoneInfoNotFoundError and friends
        p.append(f"unknown timezone {cfg.timezone!r}")

    for label, ids in (
        ("stage", [s.id for s in inp.stages]),
        ("candidate", [c.id for c in inp.candidates]),
        ("interviewer", [i.id for i in inp.interviewers]),
        ("room", [r.id for r in inp.rooms]),
    ):
        for d in _dupes(ids):
            p.append(f"duplicate {label} id {d!r}")
    for d in _dupes([s.order_index for s in inp.stages]):
        p.append(f"duplicate stage order_index {d}")

    stage_ids = {s.id for s in inp.stages}
    for s in inp.stages:
        if s.duration_minutes <= 0:
            p.append(f"stage {s.id!r}: duration_minutes must be positive")
        if s.panel_size < 1:
            p.append(f"stage {s.id!r}: panel_size must be at least 1")

    for r in inp.rooms:
        if r.capacity < 1:
            p.append(f"room {r.id!r}: capacity must be positive")
    for i in inp.interviewers:
        if i.capacity_per_day < 1:
            p.append(f"interviewer {i.id!r}: capacity_per_day must be positive")

    def check_windows(label: str, wins: tuple[Window, ...]) -> None:
        for w in wins:
            if not (_aware(w.start) and _aware(w.end)):
                p.append(f"{label}: naive datetime in availability")
            elif w.end <= w.start:
                p.append(f"{label}: availability window ends before it starts")

    for c in inp.candidates:
        for sid in c.stage_ids:
            if sid not in stage_ids:
                p.append(f"candidate {c.id!r}: unknown stage {sid!r}")
        for d in _dupes(list(c.stage_ids)):
            p.append(f"candidate {c.id!r}: stage {d!r} listed twice")
        if not _aware(c.not_before):
            p.append(f"candidate {c.id!r}: not_before must be timezone-aware")
        check_windows(f"candidate {c.id!r}", c.availability)
    for i in inp.interviewers:
        check_windows(f"interviewer {i.id!r}", i.availability)
    for r in inp.rooms:
        if r.availability is not None:
            check_windows(f"room {r.id!r}", r.availability)

    for n, b in enumerate(inp.existing):
        if not (_aware(b.start) and _aware(b.end)) or b.end <= b.start:
            p.append(f"existing booking #{n}: needs aware start < end")

    if p:
        raise InvalidScheduleInput(p)
