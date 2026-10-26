"""Persist structured MCQs and competency coverage in interview kits.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "ai_interview_kits",
        sa.Column(
            "multiple_choice_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "ai_interview_kits",
        sa.Column(
            "competencies_to_assess",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_interview_kits", "competencies_to_assess")
    op.drop_column("ai_interview_kits", "multiple_choice_questions")
