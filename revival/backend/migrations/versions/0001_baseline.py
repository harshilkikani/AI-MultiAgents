"""baseline — full schema as of M13

Revision ID: 0001
Revises:
Create Date: 2026-04-22 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("trial_leads_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stripe_customer_id", sa.String(length=128), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("external_id", name="uq_users_external_id"),
    )
    op.create_index("ix_users_external_id", "users", ["external_id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="owner"),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "workspace_id", name="uq_member_user_ws"),
    )
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("vertical", sa.String(length=32), nullable=False),
        sa.Column("avg_ticket", sa.Float(), nullable=False, server_default="680"),
        sa.Column("calendly_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("launched_at", sa.DateTime(), nullable=True),
        sa.Column("paid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trial_leads_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_campaigns_workspace_id", "campaigns", ["workspace_id"])

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("last_contact", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_leads_workspace_id", "leads", ["workspace_id"])
    op.create_index("ix_leads_campaign_id", "leads", ["campaign_id"])
    op.create_index("ix_leads_phone", "leads", ["phone"])
    op.create_index("ix_leads_state", "leads", ["state"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False, server_default="out"),
        sa.Column("scheduled_for", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("twilio_sid", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_messages_workspace_id", "messages", ["workspace_id"])
    op.create_index("ix_messages_lead_id", "messages", ["lead_id"])
    op.create_index("ix_messages_campaign_id", "messages", ["campaign_id"])
    op.create_index("ix_messages_scheduled_for", "messages", ["scheduled_for"])

    op.create_table(
        "opt_outs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("opted_out_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("proof_message_sid", sa.String(length=64), nullable=True),
        sa.Column("proof_body", sa.Text(), nullable=True),
        sa.UniqueConstraint("workspace_id", "phone", name="uq_opt_outs_ws_phone"),
    )
    op.create_index("ix_opt_outs_workspace_id", "opt_outs", ["workspace_id"])
    op.create_index("ix_opt_outs_phone", "opt_outs", ["phone"])

    op.create_table(
        "compliance_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("message_sid", sa.String(length=64), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
    )
    op.create_index("ix_compliance_events_workspace_id", "compliance_events", ["workspace_id"])
    op.create_index("ix_compliance_events_phone", "compliance_events", ["phone"])
    op.create_index("ix_compliance_events_event_type", "compliance_events", ["event_type"])
    op.create_index("ix_compliance_events_created_at", "compliance_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("compliance_events")
    op.drop_table("opt_outs")
    op.drop_table("messages")
    op.drop_table("leads")
    op.drop_table("campaigns")
    op.drop_table("workspace_members")
    op.drop_table("users")
    op.drop_table("workspaces")
