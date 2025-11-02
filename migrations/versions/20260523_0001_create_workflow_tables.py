"""create workflow tables

Revision ID: 20260523_0001
Revises:
Create Date: 2026-05-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260523_0001"
down_revision = None
branch_labels = None
depends_on = None


def workflow_timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *workflow_timestamp_columns(),
    )

    op.create_table(
        "catalog_items",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("sku", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *workflow_timestamp_columns(),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("catalog_item_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        *workflow_timestamp_columns(),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_order_status_history_order_id",
        "order_status_history",
        ["order_id"],
    )

    op.create_table(
        "document_metadata",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("document_ref", sa.String(length=256), nullable=False),
        *workflow_timestamp_columns(),
    )
    op.create_index("ix_document_metadata_order_id", "document_metadata", ["order_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("failure_reason", sa.String(length=256), nullable=True),
        *workflow_timestamp_columns(),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("recipient", sa.String(length=256), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        *workflow_timestamp_columns(),
    )
    op.create_index("ix_notifications_order_id", "notifications", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_order_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_document_metadata_order_id", table_name="document_metadata")
    op.drop_table("document_metadata")
    op.drop_index(
        "ix_order_status_history_order_id",
        table_name="order_status_history",
    )
    op.drop_table("order_status_history")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")
    op.drop_table("catalog_items")
    op.drop_table("auth_users")
