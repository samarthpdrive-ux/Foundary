from datetime import UTC, datetime

from app.extensions import db


class Claim(db.Model):
    __tablename__ = "claims"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    claimant_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    verification_answer_1 = db.Column(db.Text)
    verification_answer_2 = db.Column(db.Text)
    verification_answer_3 = db.Column(db.Text)
    status = db.Column(db.String(16), nullable=False, default="PENDING", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    item = db.relationship("Item", back_populates="claims")
    claimant = db.relationship("User", back_populates="claims")

    __table_args__ = (
        db.UniqueConstraint("item_id", "claimant_id", name="uq_claim_item_claimant"),
        db.Index("ix_claims_item_status", "item_id", "status"),
    )
