"""display name on login sessions (initials in the navigation)

Revision ID: 003
Revises: 002
Create Date: 2026-09-26
"""

import sqlalchemy as sa

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("login_sessions", sa.Column("display_name", sa.String(length=200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("login_sessions") as batch:
        batch.drop_column("display_name")
