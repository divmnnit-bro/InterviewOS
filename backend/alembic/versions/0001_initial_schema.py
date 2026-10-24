"""initial schema

Creates every InterviewOS table, enum type and constraint.

Revision ID: 0001
Revises:
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Needed for the exclusion constraints that block double bookings:
    # they combine equality on a uuid with range overlap on a tstzrange.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table('rooms',
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('location', sa.String(length=160), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('capacity > 0', name=op.f('ck_rooms_capacity_positive')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rooms')),
    sa.UniqueConstraint('name', name=op.f('uq_rooms_name'))
    )
    op.create_table('users',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('candidate', 'interviewer', 'coordinator', name='user_role'), nullable=False),
    sa.Column('status', sa.Enum('active', 'inactive', 'suspended', name='user_status'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_table('audit_events',
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_events_actor_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events'))
    )
    op.create_index(op.f('ix_audit_events_action'), 'audit_events', ['action'], unique=False)
    op.create_index(op.f('ix_audit_events_actor_id'), 'audit_events', ['actor_id'], unique=False)
    op.create_index('ix_audit_events_entity', 'audit_events', ['entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_audit_events_timestamp'), 'audit_events', ['timestamp'], unique=False)
    op.create_table('availabilities',
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('end_time > start_time', name=op.f('ck_availabilities_end_after_start')),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_availabilities_owner_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_availabilities'))
    )
    op.create_index('ix_availabilities_owner_window', 'availabilities', ['owner_id', 'start_time', 'end_time'], unique=False)
    op.create_table('candidates',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('roll_number', sa.String(length=32), nullable=True),
    sa.Column('branch', sa.String(length=64), nullable=True),
    sa.Column('cgpa', sa.Numeric(precision=4, scale=2), nullable=True),
    sa.Column('resume_url', sa.String(length=512), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_candidates_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_candidates')),
    sa.UniqueConstraint('roll_number', name=op.f('uq_candidates_roll_number'))
    )
    op.create_table('interviewers',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('skills', postgresql.ARRAY(sa.String(length=64)), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('department', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('capacity > 0', name=op.f('ck_interviewers_capacity_positive')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_interviewers_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_interviewers'))
    )
    op.create_table('notifications',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('type', sa.String(length=64), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('channel', sa.Enum('in_app', 'email', 'calendar', name='notification_channel'), nullable=False),
    sa.Column('status', sa.Enum('pending', 'sent', 'failed', name='notification_status'), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    op.create_index('ix_notifications_delivery_queue', 'notifications', ['status', 'channel'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_table('recruitment_drives',
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Enum('draft', 'collecting_availability', 'published', 'in_progress', 'completed', 'archived', name='drive_status'), nullable=False),
    sa.Column('schedule_version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('schedule_version >= 0', name=op.f('ck_recruitment_drives_schedule_version_non_negative')),
    sa.CheckConstraint('window_end > window_start', name=op.f('ck_recruitment_drives_window_valid')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_recruitment_drives_created_by_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_recruitment_drives'))
    )
    op.create_index(op.f('ix_recruitment_drives_status'), 'recruitment_drives', ['status'], unique=False)
    op.create_table('interview_stages',
    sa.Column('drive_id', sa.UUID(), nullable=False),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('stage_type', sa.Enum('coding', 'technical', 'hr', name='stage_type'), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('panel_size', sa.Integer(), nullable=False),
    sa.Column('required_skills', postgresql.ARRAY(sa.String(length=64)), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('rule', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('duration_minutes > 0', name=op.f('ck_interview_stages_duration_positive')),
    sa.CheckConstraint('order_index >= 1', name=op.f('ck_interview_stages_order_positive')),
    sa.CheckConstraint('panel_size > 0', name=op.f('ck_interview_stages_panel_size_positive')),
    sa.ForeignKeyConstraint(['drive_id'], ['recruitment_drives.id'], name=op.f('fk_interview_stages_drive_id_recruitment_drives'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_interview_stages')),
    sa.UniqueConstraint('drive_id', 'name', name='uq_interview_stages_drive_name'),
    sa.UniqueConstraint('drive_id', 'order_index', name='uq_interview_stages_drive_order')
    )
    op.create_index(op.f('ix_interview_stages_drive_id'), 'interview_stages', ['drive_id'], unique=False)
    op.create_table('drive_candidates',
    sa.Column('drive_id', sa.UUID(), nullable=False),
    sa.Column('candidate_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('active', 'rejected', 'selected', 'withdrawn', name='drive_candidate_status'), nullable=False),
    sa.Column('current_stage_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidates.user_id'], name=op.f('fk_drive_candidates_candidate_id_candidates'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['current_stage_id'], ['interview_stages.id'], name=op.f('fk_drive_candidates_current_stage_id_interview_stages'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['drive_id'], ['recruitment_drives.id'], name=op.f('fk_drive_candidates_drive_id_recruitment_drives'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('drive_id', 'candidate_id', name=op.f('pk_drive_candidates'))
    )
    op.create_index(op.f('ix_drive_candidates_candidate_id'), 'drive_candidates', ['candidate_id'], unique=False)
    op.create_table('interviews',
    sa.Column('stage_id', sa.UUID(), nullable=False),
    sa.Column('candidate_id', sa.UUID(), nullable=False),
    sa.Column('room_id', sa.UUID(), nullable=True),
    sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Enum('proposed', 'scheduled', 'confirmed', 'completed', 'cancelled', 'no_show', name='interview_status'), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('idempotency_key', sa.String(length=64), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    postgresql.ExcludeConstraint((sa.column('candidate_id'), '='), (sa.text("tstzrange(start_time, end_time, '[)')"), '&&'), where=sa.text("status NOT IN ('cancelled', 'no_show')"), using='gist', name='ex_interviews_candidate_no_overlap'),
    postgresql.ExcludeConstraint((sa.column('room_id'), '='), (sa.text("tstzrange(start_time, end_time, '[)')"), '&&'), where=sa.text("status NOT IN ('cancelled', 'no_show')"), using='gist', name='ex_interviews_room_no_overlap'),
    sa.CheckConstraint('end_time > start_time', name=op.f('ck_interviews_end_after_start')),
    sa.ForeignKeyConstraint(['candidate_id'], ['candidates.user_id'], name=op.f('fk_interviews_candidate_id_candidates'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], name=op.f('fk_interviews_room_id_rooms'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['stage_id'], ['interview_stages.id'], name=op.f('fk_interviews_stage_id_interview_stages'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_interviews')),
    sa.UniqueConstraint('id', 'start_time', 'end_time', name='uq_interviews_id_slot'),
    sa.UniqueConstraint('idempotency_key', name=op.f('uq_interviews_idempotency_key'))
    )
    op.create_index(op.f('ix_interviews_candidate_id'), 'interviews', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_interviews_room_id'), 'interviews', ['room_id'], unique=False)
    op.create_index(op.f('ix_interviews_stage_id'), 'interviews', ['stage_id'], unique=False)
    op.create_index('ix_interviews_start_end', 'interviews', ['start_time', 'end_time'], unique=False)
    op.create_index(op.f('ix_interviews_status'), 'interviews', ['status'], unique=False)
    op.create_table('evaluations',
    sa.Column('interview_id', sa.UUID(), nullable=False),
    sa.Column('interviewer_id', sa.UUID(), nullable=False),
    sa.Column('score', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('rubric', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('feedback', sa.Text(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('score >= 0 AND score <= 10', name=op.f('ck_evaluations_score_range')),
    sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], name=op.f('fk_evaluations_interview_id_interviews'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['interviewer_id'], ['interviewers.user_id'], name=op.f('fk_evaluations_interviewer_id_interviewers'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_evaluations')),
    sa.UniqueConstraint('interview_id', 'interviewer_id', name='uq_evaluations_interview_interviewer')
    )
    op.create_index(op.f('ix_evaluations_interview_id'), 'evaluations', ['interview_id'], unique=False)
    op.create_index(op.f('ix_evaluations_interviewer_id'), 'evaluations', ['interviewer_id'], unique=False)
    op.create_table('panel_assignments',
    sa.Column('interview_id', sa.UUID(), nullable=False),
    sa.Column('interviewer_id', sa.UUID(), nullable=False),
    sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    postgresql.ExcludeConstraint((sa.column('interviewer_id'), '='), (sa.text("tstzrange(start_time, end_time, '[)')"), '&&'), where=sa.text('is_active'), using='gist', name='ex_panel_assignments_interviewer_no_overlap'),
    sa.ForeignKeyConstraint(['interview_id', 'start_time', 'end_time'], ['interviews.id', 'interviews.start_time', 'interviews.end_time'], name='fk_panel_assignments_interview_slot', onupdate='CASCADE', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['interviewer_id'], ['interviewers.user_id'], name=op.f('fk_panel_assignments_interviewer_id_interviewers'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('interview_id', 'interviewer_id', name=op.f('pk_panel_assignments'))
    )
    op.create_index(op.f('ix_panel_assignments_interviewer_id'), 'panel_assignments', ['interviewer_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_panel_assignments_interviewer_id'), table_name='panel_assignments')
    op.drop_table('panel_assignments')
    op.drop_index(op.f('ix_evaluations_interviewer_id'), table_name='evaluations')
    op.drop_index(op.f('ix_evaluations_interview_id'), table_name='evaluations')
    op.drop_table('evaluations')
    op.drop_index(op.f('ix_interviews_status'), table_name='interviews')
    op.drop_index('ix_interviews_start_end', table_name='interviews')
    op.drop_index(op.f('ix_interviews_stage_id'), table_name='interviews')
    op.drop_index(op.f('ix_interviews_room_id'), table_name='interviews')
    op.drop_index(op.f('ix_interviews_candidate_id'), table_name='interviews')
    op.drop_table('interviews')
    op.drop_index(op.f('ix_drive_candidates_candidate_id'), table_name='drive_candidates')
    op.drop_table('drive_candidates')
    op.drop_index(op.f('ix_interview_stages_drive_id'), table_name='interview_stages')
    op.drop_table('interview_stages')
    op.drop_index(op.f('ix_recruitment_drives_status'), table_name='recruitment_drives')
    op.drop_table('recruitment_drives')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_index('ix_notifications_delivery_queue', table_name='notifications')
    op.drop_table('notifications')
    op.drop_table('interviewers')
    op.drop_table('candidates')
    op.drop_index('ix_availabilities_owner_window', table_name='availabilities')
    op.drop_table('availabilities')
    op.drop_index(op.f('ix_audit_events_timestamp'), table_name='audit_events')
    op.drop_index('ix_audit_events_entity', table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_actor_id'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_action'), table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('rooms')

    # Enum types are not dropped with their tables. btree_gist is left installed
    # on purpose: other schemas in the database may depend on it.
    op.execute("DROP TYPE IF EXISTS interview_status")
    op.execute("DROP TYPE IF EXISTS notification_status")
    op.execute("DROP TYPE IF EXISTS notification_channel")
    op.execute("DROP TYPE IF EXISTS drive_candidate_status")
    op.execute("DROP TYPE IF EXISTS stage_type")
    op.execute("DROP TYPE IF EXISTS drive_status")
    op.execute("DROP TYPE IF EXISTS user_status")
    op.execute("DROP TYPE IF EXISTS user_role")
