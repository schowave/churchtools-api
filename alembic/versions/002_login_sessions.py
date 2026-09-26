"""server-side login sessions

Revision ID: 002
Revises: 001
Create Date: 2026-09-26
"""

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_sessions",
        sa.Column("id_hash", sa.String(length=64), nullable=False),
        sa.Column("login_token", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id_hash"),
    )
    op.create_index("ix_login_sessions_expires_at", "login_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_login_sessions_expires_at", table_name="login_sessions")
    op.drop_table("login_sessions")
