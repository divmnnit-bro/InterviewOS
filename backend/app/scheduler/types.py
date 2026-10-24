"""Plain-data input and output types for the scheduler.

Nothing here imports SQLAlchemy, FastAPI or the database. The service layer
converts ORM rows into these dataclasses, calls `solve`, and converts the
result back. All datetimes must be timezone-aware.
"""
from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo

Id = Hashable  # uuid.UUID or str; only equality and hashing are used


@dataclass(frozen=True)
class Window:
    """Half-open time window [start, end)."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class StageSpec:
    id: Id
    order_index: int
    duration_minutes: int
    panel_size: int = 1
    required_skills: frozenset[str] = frozenset()
    name: str = ""


@dataclass(frozen=True)
class CandidateSpec:
    """A candidate and the round(s) to schedule in this run.

    `stage_ids` is normally a single stage (the candidate's current round).
    If several are given they are scheduled in `order_index` order.
    `not_before` is the earliest the first round may start, for example the
    time results for the previous round were published.
    """

    id: Id
    stage_ids: tuple[Id, ...]
    availability: tuple[Window, ...]
    not_before: datetime | None = None


@dataclass(frozen=True)
class InterviewerSpec:
    id: Id
    skills: frozenset[str]
    availability: tuple[Window, ...]
    capacity_per_day: int = 4


@dataclass(frozen=True)
class RoomSpec:
    id: Id
    capacity: int  # people, including the candidate
    name: str = ""
    availability: tuple[Window, ...] | None = None  # None = open for the whole horizon


@dataclass(frozen=True)
class ExistingBooking:
    """An already-saved interview that this run must schedule around."""

    start: datetime
    end: datetime
    candidate_id: Id | None = None
    room_id: Id | None = None
    interviewer_ids: tuple[Id, ...] = ()


@dataclass(frozen=True)
class Weights:
    """Soft-preference weights. All are integers; 0 switches a term off.

    Scheduling an interview is worth far more than any combination of the
    other terms, so the solver never drops an interview to win on a preference.
    """

    scheduled: int = 1_000_000
    earliness: int = 10        # per slot of delay from the horizon start
    load_balance: int = 200    # per interview on the busiest interviewer
    room_fit: int = 5          # per spare seat in the room used


@dataclass(frozen=True)
class Anchor:
    """An interview's current placement. The solver prefers to keep it as is."""

    start: datetime
    room_id: Id
    interviewer_ids: tuple[Id, ...]


@dataclass(frozen=True)
class DisruptionWeights:
    """Cost of changing an anchored interview. Used by Ripple Rescue.

    Changing the time or room reaches the candidate, so it costs most; swapping
    a panel member is internal and costs least. Scheduling an interview still
    outranks all of these, so nobody is dropped just to avoid moving others.
    """

    time_change: int = 1000
    room_change: int = 300
    panel_change: int = 50      # per interviewer swapped out
    shift_per_slot: int = 2     # prefer small time shifts over big ones


@dataclass(frozen=True)
class SchedulerConfig:
    horizon_start: datetime
    horizon_end: datetime
    slot_minutes: int = 15
    timezone: str = "UTC"            # defines what "a day" means for daily capacity
    interviewer_buffer_minutes: int = 0   # rest an interviewer needs after a session
    min_round_gap_minutes: int = 0        # gap between two rounds of one candidate
    weights: Weights = field(default_factory=Weights)
    time_limit_seconds: float = 10.0
    workers: int = 1                 # 1 is deterministic; raise for big drives
    seed: int = 0

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@dataclass(frozen=True)
class ScheduleInput:
    stages: tuple[StageSpec, ...]
    candidates: tuple[CandidateSpec, ...]
    interviewers: tuple[InterviewerSpec, ...]
    rooms: tuple[RoomSpec, ...]
    config: SchedulerConfig
    existing: tuple[ExistingBooking, ...] = ()


# ----------------------------------------------------------------- output


@dataclass(frozen=True)
class ProposedInterview:
    candidate_id: Id
    stage_id: Id
    start: datetime
    end: datetime
    room_id: Id
    interviewer_ids: tuple[Id, ...]


class ReasonCode(str, Enum):
    NO_QUALIFIED_INTERVIEWERS = "no_qualified_interviewers"
    NOT_ENOUGH_QUALIFIED_INTERVIEWERS = "not_enough_qualified_interviewers"
    NO_ROOM_LARGE_ENOUGH = "no_room_large_enough"
    CANDIDATE_NO_AVAILABILITY = "candidate_no_availability"
    CANDIDATE_WINDOWS_TOO_SHORT = "candidate_windows_too_short"
    NO_INTERVIEWER_OVERLAP = "no_interviewer_overlap"
    NO_ROOM_OVERLAP = "no_room_overlap"
    PREVIOUS_ROUND_UNSCHEDULED = "previous_round_unscheduled"
    CAPACITY_CONTENTION = "capacity_contention"   # fits alone, lost to other demand
    SOLVER_TIMEOUT = "solver_timeout"             # no solution found in the time limit


@dataclass(frozen=True)
class Reason:
    code: ReasonCode
    detail: str


@dataclass(frozen=True)
class Unscheduled:
    candidate_id: Id
    stage_id: Id
    reasons: tuple[Reason, ...]


class SolveStatus(str, Enum):
    OPTIMAL = "optimal"        # proven best under the weights
    FEASIBLE = "feasible"      # valid, time limit hit before proof
    HEURISTIC = "heuristic"    # solver ran out of time; this is the quick first-fit schedule
    NOTHING_TO_SCHEDULE = "nothing_to_schedule"
    UNKNOWN = "unknown"        # time limit hit with no solution


@dataclass(frozen=True)
class ScheduleResult:
    status: SolveStatus
    interviews: tuple[ProposedInterview, ...]
    unscheduled: tuple[Unscheduled, ...]
    objective: int | None = None
    wall_time_seconds: float = 0.0
    load_per_interviewer: dict[Id, int] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return not self.unscheduled
