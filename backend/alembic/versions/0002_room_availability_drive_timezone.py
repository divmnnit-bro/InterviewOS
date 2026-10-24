"""room availability windows and drive timezone

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recruitment_drives",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
    )
    op.create_table(
        "room_availabilities",
        sa.Column("room_id", sa.UUID(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("end_time > start_time", name=op.f("ck_room_availabilities_end_after_start")),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name=op.f("fk_room_availabilities_room_id_rooms"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_room_availabilities")),
    )
    op.create_index("ix_room_availabilities_room_window", "room_availabilities", ["room_id", "start_time", "end_time"])


def downgrade() -> None:
    op.drop_index("ix_room_availabilities_room_window", table_name="room_availabilities")
    op.drop_table("room_availabilities")
    op.drop_column("recruitment_drives", "timezone")
