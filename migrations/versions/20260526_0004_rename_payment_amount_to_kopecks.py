"""rename payment amount to kopecks

Revision ID: 20260526_0004
Revises: 20260526_0003
Create Date: 2026-05-26 00:00:00.000000
"""

from alembic import op


revision = "20260526_0004"
down_revision = "20260526_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "payments",
        "amount_cents",
        new_column_name="amount_kopecks",
    )


def downgrade() -> None:
    op.alter_column(
        "payments",
        "amount_kopecks",
        new_column_name="amount_cents",
    )
