"""Pass/fail and progress rules. Pure functions: no database, no web framework.

Kept apart from the services so the rules can be tested on their own.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class StageState(str, Enum):
    """Where one candidate stands in one round of a drive."""

    NOT_REACHED = "not_reached"
    PENDING = "pending"                        # current round, no interview yet
    INTERVIEWING = "interviewing"              # current round, interview booked or feedback still due
    AWAITING_DECISION = "awaiting_decision"    # every panelist has given feedback; coordinator to decide
    PASSED = "passed"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


def average(scores: list[float]) -> float | None:
    """Mean of the evaluators' overall scores, to two decimals; None when there are none."""
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def rule_met(rule: dict[str, Any] | None, avg: float | None) -> bool | None:
    """Does `avg` satisfy the stage's pass rule?

    Returns None when it cannot be decided automatically: no scores yet, a rule type this
    code does not know, or a malformed threshold. None never blocks a coordinator.
    """
    if not rule or rule.get("type") != "min_score" or avg is None:
        return None
    threshold = rule.get("min_score")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        return None
    return avg >= float(threshold)


def evaluations_complete(panel: set, evaluated: set) -> bool:
    """True when the panel is non-empty and every active panelist has given feedback."""
    return bool(panel) and not (panel - evaluated)


def decision_blockers(
    *,
    has_interview: bool,
    panel: set,
    evaluated: set,
    avg: float | None,
    rule: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Reasons a PASS should not go through without an explicit override. Empty list = clear."""
    if not has_interview:
        return [{"code": "no_interview", "detail": "No interview has taken place for this round."}]
    blockers: list[dict[str, str]] = []
    if not evaluations_complete(panel, evaluated):
        missing = len(panel - evaluated)
        blockers.append({
            "code": "evaluations_incomplete",
            "detail": (f"{missing} of {len(panel)} panel members have not submitted feedback."
                       if panel else "The interview has no active panel members."),
        })
    if rule_met(rule, avg) is False:
        blockers.append({
            "code": "rule_not_met",
            "detail": f"Average score {avg} is below the round's minimum of {rule['min_score']}.",
        })
    return blockers


def stage_state(
    *,
    enrollment_status: str,
    stage_index: int,
    current_index: int,
    has_interview: bool,
    feedback_complete: bool,
) -> StageState:
    """State of one round for one candidate. Indexes are positions in the drive's stage order."""
    if enrollment_status == "selected":
        return StageState.PASSED
    if stage_index < current_index:
        return StageState.PASSED
    if stage_index > current_index:
        return StageState.NOT_REACHED
    if enrollment_status == "rejected":
        return StageState.REJECTED
    if enrollment_status == "withdrawn":
        return StageState.WITHDRAWN
    if not has_interview:
        return StageState.PENDING
    return StageState.AWAITING_DECISION if feedback_complete else StageState.INTERVIEWING
