"""Add per-participant consent for admin chat review.

Revision ID: e81a47c9fd30
Revises: c72d9a63f114
Create Date: 2026-10-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "e81a47c9fd30"
down_revision = "c72d9a63f114"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("conversation_consents"):
        op.create_table(
            "conversation_consents",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("peer_id", sa.Integer(), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("user_id <> peer_id", name="ck_conversation_consent_distinct_users"),
            sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["peer_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "peer_id", "item_id", name="uq_conversation_consent_participant"),
        )

    existing_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("conversation_consents")}
    if "ix_conversation_consents_allowed" not in existing_indexes:
        op.create_index(
            "ix_conversation_consents_allowed",
            "conversation_consents",
            ["allowed", "item_id"],
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("conversation_consents"):
        indexes = {index["name"] for index in inspector.get_indexes("conversation_consents")}
        if "ix_conversation_consents_allowed" in indexes:
            op.drop_index("ix_conversation_consents_allowed", table_name="conversation_consents")
        op.drop_table("conversation_consents")
