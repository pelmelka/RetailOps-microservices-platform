"""align catalog and order money to kopecks

Revision ID: 20260526_0005
Revises: 20260526_0004
Create Date: 2026-05-26 00:00:00.000000
"""

from alembic import op


revision = "20260526_0005"
down_revision = "20260526_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "catalog_items",
        "price_cents",
        new_column_name="price_kopecks",
    )
    op.alter_column(
        "orders",
        "total_cents",
        new_column_name="total_kopecks",
    )


def downgrade() -> None:
    op.alter_column(
        "orders",
        "total_kopecks",
        new_column_name="total_cents",
    )
    op.alter_column(
        "catalog_items",
        "price_kopecks",
        new_column_name="price_cents",
    )
