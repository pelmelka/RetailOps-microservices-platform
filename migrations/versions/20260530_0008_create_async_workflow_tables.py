"""create async workflow tables

Revision ID: 20260530_0008
Revises: 20260526_0007
Create Date: 2026-05-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260530_0008"
down_revision = "20260526_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("workflow_type", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("user_email", sa.String(length=256), nullable=True),
        sa.Column("order_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("current_step", sa.String(length=64), nullable=True),
        sa.Column("failed_step", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.String(length=1024), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        sa.Column("catalog_item_id", sa.String(length=128), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("invoice_document_id", sa.String(length=128), nullable=True),
        sa.Column("receipt_document_id", sa.String(length=128), nullable=True),
        sa.Column("payment_id", sa.String(length=128), nullable=True),
        sa.Column("notification_id", sa.String(length=128), nullable=True),
        sa.Column("payment_scenario", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_workflow_runs_user_idempotency_key",
        ),
    )
    op.create_index("ix_workflow_runs_user_id", "workflow_runs", ["user_id"])
    op.create_index("ix_workflow_runs_order_id", "workflow_runs", ["order_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])

    op.create_table(
        "processed_stream_messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("stream_name", sa.String(length=128), nullable=False),
        sa.Column("group_name", sa.String(length=128), nullable=False),
        sa.Column("consumer_name", sa.String(length=128), nullable=False),
        sa.Column("redis_message_id", sa.String(length=128), nullable=False),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("message_type", sa.String(length=128), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("order_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("error", sa.String(length=1024), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "stream_name",
            "group_name",
            "consumer_name",
            "redis_message_id",
            name="uq_processed_stream_messages_consumer_message",
        ),
    )
    op.create_index(
        "ix_processed_stream_messages_workflow_id",
        "processed_stream_messages",
        ["workflow_id"],
    )
    op.create_index(
        "ix_processed_stream_messages_order_id",
        "processed_stream_messages",
        ["order_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_processed_stream_messages_order_id",
        table_name="processed_stream_messages",
    )
    op.drop_index(
        "ix_processed_stream_messages_workflow_id",
        table_name="processed_stream_messages",
    )
    op.drop_table("processed_stream_messages")
    op.drop_index("ix_workflow_runs_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_order_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_user_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")
