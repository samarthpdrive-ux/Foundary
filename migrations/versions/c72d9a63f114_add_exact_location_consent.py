"""Add reporter opt-in for exact lost-item locations.

Revision ID: c72d9a63f114
Revises: b671dd9b4546
Create Date: 2026-10-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "c72d9a63f114"
down_revision = "b671dd9b4546"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("items"):
        return
    existing_columns = {column["name"] for column in inspector.get_columns("items")}
    if "share_exact_location" not in existing_columns:
        op.add_column(
            "items",
            sa.Column(
                "share_exact_location",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("items"):
        existing_columns = {column["name"] for column in inspector.get_columns("items")}
        if "share_exact_location" in existing_columns:
            op.drop_column("items", "share_exact_location")
