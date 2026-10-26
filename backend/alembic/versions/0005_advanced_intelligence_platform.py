"""advanced intelligence platform: jobs, ai interview kits, and stage rubric templates

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add rubric_template to interview_stages
    op.add_column(
        "interview_stages",
        sa.Column("rubric_template", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # 2. Create jobs table
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_jobs_job_type", "jobs", ["job_type"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_creator_id", "jobs", ["creator_id"])
    op.create_index("ix_jobs_idempotency_key", "jobs", ["idempotency_key"], unique=True)

    # 3. Create ai_interview_kits table
    op.create_table(
        "ai_interview_kits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("drive_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recruitment_drives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interview_stages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic", sa.String(length=128), nullable=False),
        sa.Column("difficulty", sa.String(length=32), nullable=False, server_default="intermediate"),
        sa.Column("coding_challenges", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("system_design_scenarios", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("behavioral_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("rubric_template", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("provider_used", sa.String(length=64), nullable=False, server_default="deterministic"),
        sa.Column("model_used", sa.String(length=64), nullable=False, server_default="local"),
        sa.Column("raw_prompt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_interview_kits_drive_id", "ai_interview_kits", ["drive_id"])
    op.create_index("ix_ai_interview_kits_stage_id", "ai_interview_kits", ["stage_id"])


def downgrade() -> None:
    op.drop_table("ai_interview_kits")
    op.drop_table("jobs")
    op.drop_column("interview_stages", "rubric_template")
