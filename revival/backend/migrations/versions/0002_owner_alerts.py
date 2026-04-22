"""owner alerts — M16

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-22 01:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Batch mode for SQLite; no-op extra ceremony on Postgres.
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.add_column(sa.Column("owner_phone", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("owner_email", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("owner_timezone", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("slack_webhook_url", sa.String(length=500), nullable=True))

    op.create_table(
        "owner_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("twilio_sid", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="sent"),
    )
    op.create_index("ix_owner_alerts_workspace_id", "owner_alerts", ["workspace_id"])
    op.create_index("ix_owner_alerts_lead_id", "owner_alerts", ["lead_id"])
    op.create_index("ix_owner_alerts_campaign_id", "owner_alerts", ["campaign_id"])
    op.create_index("ix_owner_alerts_alert_type", "owner_alerts", ["alert_type"])
    op.create_index("ix_owner_alerts_sent_at", "owner_alerts", ["sent_at"])


def downgrade() -> None:
    op.drop_table("owner_alerts")
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.drop_column("slack_webhook_url")
        batch_op.drop_column("owner_timezone")
        batch_op.drop_column("owner_email")
        batch_op.drop_column("owner_phone")
