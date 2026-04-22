"""campaign pause flag — M17

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-22 02:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("campaigns") as batch_op:
        batch_op.add_column(sa.Column("paused", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("paused_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("campaigns") as batch_op:
        batch_op.drop_column("paused_at")
        batch_op.drop_column("paused")
