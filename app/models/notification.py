from datetime import UTC, datetime

from app.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(32), nullable=False, default="GENERAL")
    related_item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="SET NULL"))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    user = db.relationship("User", back_populates="notifications")
    related_item = db.relationship("Item", back_populates="notifications")

    __table_args__ = (db.Index("ix_notifications_user_read_created", "user_id", "is_read", "created_at"),)
