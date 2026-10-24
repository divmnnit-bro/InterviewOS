"""Pure-logic interview scheduler (OR-Tools CP-SAT). No database or web imports."""
from app.scheduler.solver import solve
from app.scheduler.types import (
    CandidateSpec,
    ExistingBooking,
    InterviewerSpec,
    ProposedInterview,
    Reason,
    ReasonCode,
    RoomSpec,
    ScheduleInput,
    ScheduleResult,
    SchedulerConfig,
    SolveStatus,
    StageSpec,
    Unscheduled,
    Weights,
    Window,
)
from app.scheduler.validation import InvalidScheduleInput, validate_input

__all__ = [
    "solve", "validate_input", "InvalidScheduleInput",
    "CandidateSpec", "ExistingBooking", "InterviewerSpec", "ProposedInterview", "Reason",
    "ReasonCode", "RoomSpec", "ScheduleInput", "ScheduleResult", "SchedulerConfig",
    "SolveStatus", "StageSpec", "Unscheduled", "Weights", "Window",
]
