"""Errors raised by the service layer. main.py turns them into JSON responses."""
from __future__ import annotations


class ServiceError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: object | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFound(ServiceError):
    status_code = 404
    code = "not_found"


class Conflict(ServiceError):
    status_code = 409
    code = "conflict"


class StaleScheduleVersion(Conflict):
    code = "stale_schedule_version"


class PlanChanged(Conflict):
    """The repair computed now is not the one the coordinator previewed."""

    code = "plan_changed"


class Forbidden(ServiceError):
    status_code = 403
    code = "forbidden"


class Unprocessable(ServiceError):
    status_code = 422
    code = "unprocessable"


class InvalidLink(ServiceError):
    status_code = 401
    code = "invalid_link"


class SlotUnavailable(Conflict):
    """The chosen slot cannot be booked (taken, or no longer valid when rechecked)."""

    code = "slot_unavailable"


class IdempotencyMismatch(Unprocessable):
    code = "idempotency_key_reused"


class DecisionBlocked(Conflict):
    """A pass decision lacks the evidence it needs; `details` lists what is missing."""

    code = "decision_blocked"


class EvaluationLocked(Conflict):
    """The candidate's result for this round is already recorded, so feedback can no longer change."""

    code = "evaluation_locked"
