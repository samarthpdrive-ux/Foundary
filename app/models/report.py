from datetime import UTC, datetime

from app.extensions import db


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reported_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="SET NULL"), index=True)
    reason = db.Column(db.String(60), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="PENDING", index=True)
    admin_note = db.Column(db.Text)
    action_taken = db.Column(db.String(32))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    reporter = db.relationship("User", foreign_keys=[reporter_id])
    reported_user = db.relationship("User", foreign_keys=[reported_user_id])
    item = db.relationship("Item", back_populates="reports")
