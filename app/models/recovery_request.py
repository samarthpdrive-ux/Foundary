from datetime import UTC, datetime

from app.extensions import db


class RecoveryRequest(db.Model):
    __tablename__ = "recovery_requests"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    contact_email = db.Column(db.String(255))
    is_resolved = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    item = db.relationship("Item", back_populates="recovery_requests")
