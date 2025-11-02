"""harden provider boundaries

Revision ID: 20260526_0003
Revises: 20260525_0002
Create Date: 2026-05-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260526_0003"
down_revision = "20260525_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_metadata",
        sa.Column("document_number", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "document_metadata",
        sa.Column("document_title", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "document_metadata",
        sa.Column("content_type", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "document_metadata",
        sa.Column("storage_path", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "document_metadata",
        sa.Column("size_bytes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_metadata",
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "document_metadata",
        sa.Column("generator", sa.String(length=128), nullable=True),
    )

    op.add_column(
        "payments",
        sa.Column("payment_method", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("provider", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("provider_reference", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("provider_scenario", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("failure_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "notifications",
        sa.Column("template_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("subject", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("provider", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("provider_reference", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column(
            "delivery_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "notifications",
        sa.Column("last_error", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "last_error")
    op.drop_column("notifications", "delivery_attempts")
    op.drop_column("notifications", "sent_at")
    op.drop_column("notifications", "provider_reference")
    op.drop_column("notifications", "provider")
    op.drop_column("notifications", "subject")
    op.drop_column("notifications", "template_key")

    op.drop_column("payments", "processed_at")
    op.drop_column("payments", "failure_code")
    op.drop_column("payments", "provider_scenario")
    op.drop_column("payments", "provider_reference")
    op.drop_column("payments", "provider")
    op.drop_column("payments", "payment_method")

    op.drop_column("document_metadata", "generator")
    op.drop_column("document_metadata", "checksum_sha256")
    op.drop_column("document_metadata", "size_bytes")
    op.drop_column("document_metadata", "storage_path")
    op.drop_column("document_metadata", "content_type")
    op.drop_column("document_metadata", "document_title")
    op.drop_column("document_metadata", "document_number")
