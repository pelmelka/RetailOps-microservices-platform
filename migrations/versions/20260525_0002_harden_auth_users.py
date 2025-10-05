"""harden auth users

Revision ID: 20260525_0002
Revises: 20260523_0001
Create Date: 2026-05-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260525_0002"
down_revision = "20260523_0001"
branch_labels = None
depends_on = None


LOCAL_WORKFLOW_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$/mT+uwydb4yZrut/OL2C4Q"
    "$nr2BDN6gP6wecqJCGKcHSmBWjVEs3LFpZItDIdOtdpo"
)


def upgrade() -> None:
    op.add_column(
        "auth_users",
        sa.Column("email", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "auth_users",
        sa.Column("password_hash", sa.String(length=512), nullable=True),
    )

    op.execute(
        """
        UPDATE auth_users
        SET email = lower(username) || '@example.test'
        WHERE email IS NULL
        """
    )
    op.execute(
        """
        UPDATE auth_users
        SET email = 'local-user@example.test'
        WHERE id = 'user-local-001'
        """
    )
    op.execute(
        sa.text(
            """
            UPDATE auth_users
            SET password_hash = :password_hash
            WHERE password_hash IS NULL
            """
        ).bindparams(password_hash=LOCAL_WORKFLOW_PASSWORD_HASH)
    )

    op.alter_column("auth_users", "email", nullable=False)
    op.alter_column("auth_users", "password_hash", nullable=False)
    op.create_index("ux_auth_users_email", "auth_users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_auth_users_email", table_name="auth_users")
    op.drop_column("auth_users", "password_hash")
    op.drop_column("auth_users", "email")
