"""Pass/fail rules. No database needed."""
import pytest
from pydantic import ValidationError

from app.services.pipeline_rules import (
    StageState,
    average,
    decision_blockers,
    evaluations_complete,
    rule_met,
    stage_state,
)
from app.schemas.drive import StageCreate

RULE = {"type": "min_score", "min_score": 6.0}


def test_average():
    assert average([]) is None
    assert average([8, 6, 7]) == 7.0
    assert average([7, 8]) == 7.5
    assert average([1, 2, 2]) == 1.67


def test_rule_met_boundaries_and_unknowns():
    assert rule_met(RULE, 6.0) is True and rule_met(RULE, 5.99) is False
    assert rule_met(RULE, None) is None
    assert rule_met({"type": "panel_vote"}, 9) is None          # unknown rule type: not auto-decidable
    assert rule_met({"type": "min_score", "min_score": "six"}, 9) is None
    assert rule_met({"type": "min_score", "min_score": True}, 9) is None
    assert rule_met(None, 9) is None


def test_evaluations_complete_needs_a_panel_and_everyone():
    assert evaluations_complete({"a"}, {"a", "x"})
    assert not evaluations_complete({"a", "b"}, {"a"})
    assert not evaluations_complete(set(), {"a"})


def codes(**kw):
    base = dict(has_interview=True, panel={"a"}, evaluated={"a"}, avg=7.0, rule=RULE)
    base.update(kw)
    return [b["code"] for b in decision_blockers(**base)]


def test_blockers():
    assert codes() == []
    assert codes(has_interview=False) == ["no_interview"]
    assert codes(evaluated=set(), avg=None) == ["evaluations_incomplete"]
    assert codes(avg=3.0) == ["rule_not_met"]
    assert codes(panel={"a", "b"}, evaluated={"a"}, avg=3.0) == ["evaluations_incomplete", "rule_not_met"]
    assert codes(rule={"type": "unknown"}, avg=0.0) == ["unsupported_rule"]


def test_stage_rules_reject_unimplemented_and_invalid_types():
    base = dict(order_index=1, name="Tech", stage_type="technical", duration_minutes=30)
    assert StageCreate(**base, rule={"type": "min_score", "min_score": 7}).rule["min_score"] == 7
    for rule in (
        {"type": "panel_vote"},
        {"type": "min_score", "min_score": True},
        {"type": "min_score", "min_score": 11},
        {"type": "min_score", "min_score": float("nan")},
    ):
        with pytest.raises(ValidationError):
            StageCreate(**base, rule=rule)


def state(status, stage, current, interview=False, done=False):
    return stage_state(enrollment_status=status, stage_index=stage, current_index=current,
                       has_interview=interview, feedback_complete=done)


def test_stage_states():
    assert state("active", 0, 1) is StageState.PASSED
    assert state("active", 2, 1) is StageState.NOT_REACHED
    assert state("active", 1, 1) is StageState.PENDING
    assert state("active", 1, 1, interview=True) is StageState.INTERVIEWING
    assert state("active", 1, 1, interview=True, done=True) is StageState.AWAITING_DECISION
    assert state("rejected", 1, 1) is StageState.REJECTED and state("rejected", 2, 1) is StageState.NOT_REACHED
    assert state("withdrawn", 1, 1) is StageState.WITHDRAWN
    assert all(state("selected", i, 1) is StageState.PASSED for i in range(3))
