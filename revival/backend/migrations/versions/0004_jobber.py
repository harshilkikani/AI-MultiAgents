"""jobber connection + lead external id — M18

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-22 03:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(sa.Column("external_source", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("external_id", sa.String(length=128), nullable=True))
    op.create_index("ix_leads_external_source", "leads", ["external_source"])
    op.create_index("ix_leads_external_id", "leads", ["external_id"])

    op.create_table(
        "jobber_connections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("account_name", sa.String(length=200), nullable=True),
        sa.Column("access_token", sa.String(length=2048), nullable=False),
        sa.Column("refresh_token", sa.String(length=2048), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("scopes", sa.String(length=500), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_sync_stats", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.UniqueConstraint("workspace_id", name="uq_jobber_workspace"),
    )
    op.create_index("ix_jobber_connections_workspace_id", "jobber_connections", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("jobber_connections")
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_column("external_id")
        batch_op.drop_column("external_source")
