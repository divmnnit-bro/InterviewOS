"""drive scheduling rules (slot grid, interviewer rest, round gap)

Self-booking must apply the same rules as the solver, so they are stored on the drive.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for name, default in (("slot_minutes", "15"), ("interviewer_buffer_minutes", "0"), ("min_round_gap_minutes", "0")):
        op.add_column("recruitment_drives", sa.Column(name, sa.Integer(), nullable=False, server_default=default))
    op.create_check_constraint(op.f("ck_recruitment_drives_slot_minutes_range"), "recruitment_drives",
                               "slot_minutes BETWEEN 5 AND 60")
    op.create_check_constraint(op.f("ck_recruitment_drives_rules_non_negative"), "recruitment_drives",
                               "interviewer_buffer_minutes >= 0 AND min_round_gap_minutes >= 0")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_recruitment_drives_rules_non_negative"), "recruitment_drives", type_="check")
    op.drop_constraint(op.f("ck_recruitment_drives_slot_minutes_range"), "recruitment_drives", type_="check")
    for name in ("min_round_gap_minutes", "interviewer_buffer_minutes", "slot_minutes"):
        op.drop_column("recruitment_drives", name)
