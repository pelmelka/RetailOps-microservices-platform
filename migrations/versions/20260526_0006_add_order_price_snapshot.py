"""add order price snapshot

Revision ID: 20260526_0006
Revises: 20260526_0005
Create Date: 2026-05-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260526_0006"
down_revision = "20260526_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("quantity", sa.Integer(), nullable=True))
    op.add_column(
        "orders",
        sa.Column("unit_price_kopecks", sa.Integer(), nullable=True),
    )

    op.execute(
        """
        UPDATE orders
        SET quantity = 1,
            unit_price_kopecks = total_kopecks
        WHERE quantity IS NULL OR unit_price_kopecks IS NULL
        """
    )

    op.alter_column("orders", "quantity", nullable=False)
    op.alter_column("orders", "unit_price_kopecks", nullable=False)

    op.create_check_constraint(
        "ck_orders_quantity_positive",
        "orders",
        "quantity > 0",
    )
    op.create_check_constraint(
        "ck_orders_unit_price_kopecks_non_negative",
        "orders",
        "unit_price_kopecks >= 0",
    )
    op.create_check_constraint(
        "ck_orders_total_kopecks_non_negative",
        "orders",
        "total_kopecks >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_orders_total_kopecks_non_negative",
        "orders",
        type_="check",
    )
    op.drop_constraint(
        "ck_orders_unit_price_kopecks_non_negative",
        "orders",
        type_="check",
    )
    op.drop_constraint(
        "ck_orders_quantity_positive",
        "orders",
        type_="check",
    )
    op.drop_column("orders", "unit_price_kopecks")
    op.drop_column("orders", "quantity")
