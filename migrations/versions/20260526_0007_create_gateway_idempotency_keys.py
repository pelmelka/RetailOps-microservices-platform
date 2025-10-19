"""create gateway idempotency keys

Revision ID: 20260526_0007
Revises: 20260526_0006
Create Date: 2026-05-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260526_0007"
down_revision = "20260526_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gateway_idempotency_keys",
        sa.Column("id", sa.String(length=128), primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column(
            "response_body",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            "method",
            "path",
            name="uq_gateway_idempotency_scope",
        ),
    )


def downgrade() -> None:
    op.drop_table("gateway_idempotency_keys")
