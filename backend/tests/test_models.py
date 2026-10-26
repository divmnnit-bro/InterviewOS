"""Schema-level checks. These need no database."""

import re

from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import configure_mappers

from app.db.base import Base
from app.models import InterviewStatus

EXPECTED_TABLES = {
    "users", "candidates", "interviewers", "rooms",
    "recruitment_drives", "interview_stages", "drive_candidates",
    "availabilities", "interviews", "panel_assignments",
    "evaluations", "audit_events", "notifications", "room_availabilities",
    "jobs", "ai_interview_kits",
}


def test_mappers_configure():
    configure_mappers()


def test_all_tables_present():
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_enum_columns_store_values_not_names():
    """Regression test: SQLAlchemy stores member NAMES by default ('CANCELLED').

    The exclusion constraints filter on lowercase values, so the database labels
    must be the values. pg_enum() guarantees that.
    """
    checked = 0
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, SAEnum) and column.type.enum_class is not None:
                expected = [m.value for m in column.type.enum_class]
                assert list(column.type.enums) == expected, f"{table.name}.{column.name}"
                checked += 1
    assert checked == 9


def test_overlap_constraints_only_use_real_enum_labels():
    """Every quoted label in an exclusion WHERE clause must be a real enum value."""
    interview_labels = {m.value for m in InterviewStatus}
    interviews = Base.metadata.tables["interviews"]
    exclusions = [c for c in interviews.constraints if isinstance(c, ExcludeConstraint)]
    assert len(exclusions) == 2
    for constraint in exclusions:
        used = set(re.findall(r"'([a-z_]+)'", str(constraint.where)))
        assert used and used <= interview_labels


def test_every_overlap_rule_has_a_constraint():
    def names(table):
        return {c.name for c in Base.metadata.tables[table].constraints
                if isinstance(c, ExcludeConstraint)}

    assert names("interviews") == {
        "ex_interviews_room_no_overlap",
        "ex_interviews_candidate_no_overlap",
    }
    assert names("panel_assignments") == {"ex_panel_assignments_interviewer_no_overlap"}


def test_panel_slot_foreign_key_targets_unique_slot():
    panel = Base.metadata.tables["panel_assignments"]
    interviews = Base.metadata.tables["interviews"]
    fk = next(c for c in panel.foreign_key_constraints if c.name == "fk_panel_assignments_interview_slot")
    assert fk.onupdate == "CASCADE"
    assert [e.column.name for e in fk.elements] == ["id", "start_time", "end_time"]
    assert any(
        c.name == "uq_interviews_id_slot" for c in interviews.constraints
    )
