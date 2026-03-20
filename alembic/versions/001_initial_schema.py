"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-15
"""

import sqlalchemy as sa

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("additional_info", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_table(
        "color_settings",
        sa.Column("setting_name", sa.String(), nullable=False),
        sa.Column("background_color", sa.String(), nullable=False),
        sa.Column("background_alpha", sa.Integer(), nullable=False),
        sa.Column("date_color", sa.String(), nullable=False),
        sa.Column("description_color", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("setting_name"),
        if_not_exists=True,
    )
    op.create_table(
        "logo_settings",
        sa.Column("setting_name", sa.String(), nullable=False),
        sa.Column("logo_data", sa.LargeBinary(), nullable=True),
        sa.Column("logo_filename", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("setting_name"),
        if_not_exists=True,
    )
    op.create_table(
        "background_image_settings",
        sa.Column("setting_name", sa.String(), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=True),
        sa.Column("image_filename", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("setting_name"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("background_image_settings")
    op.drop_table("logo_settings")
    op.drop_table("color_settings")
    op.drop_table("appointments")
