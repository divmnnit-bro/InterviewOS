"""evaluation recommendation

Adds the interviewer's overall verdict (strong_hire / hire / no_hire / strong_no_hire) to evaluations.
The column is nullable so existing rows stay valid; the API requires it for every new evaluation.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALUES = ("strong_hire", "hire", "no_hire", "strong_no_hire")


def upgrade() -> None:
    postgresql.ENUM(*_VALUES, name="evaluation_recommendation").create(op.get_bind(), checkfirst=True)
    op.add_column(
        "evaluations",
        sa.Column(
            "recommendation",
            postgresql.ENUM(*_VALUES, name="evaluation_recommendation", create_type=False),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("evaluations", "recommendation")
    postgresql.ENUM(name="evaluation_recommendation").drop(op.get_bind(), checkfirst=True)
