from datetime import UTC, datetime

from app.extensions import db


class ConversationConsent(db.Model):
    """Per-participant permission for admins to review one private conversation."""

    __tablename__ = "conversation_consents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    peer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    allowed = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    user = db.relationship("User", foreign_keys=[user_id])
    peer = db.relationship("User", foreign_keys=[peer_id])
    item = db.relationship("Item")

    __table_args__ = (
        db.UniqueConstraint("user_id", "peer_id", "item_id", name="uq_conversation_consent_participant"),
        db.CheckConstraint("user_id <> peer_id", name="ck_conversation_consent_distinct_users"),
        db.Index("ix_conversation_consents_allowed", "allowed", "item_id"),
    )
