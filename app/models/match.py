from datetime import UTC, datetime

from app.extensions import db


class ItemMatch(db.Model):
    __tablename__ = "item_matches"

    id = db.Column(db.Integer, primary_key=True)
    lost_item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    found_item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    score = db.Column(db.Float, nullable=False, default=0)
    image_score = db.Column(db.Float)
    match_reason = db.Column(db.Text)
    status = db.Column(db.String(16), nullable=False, default="SUGGESTED")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    lost_item = db.relationship("Item", foreign_keys=[lost_item_id], back_populates="matches_as_lost")
    found_item = db.relationship("Item", foreign_keys=[found_item_id], back_populates="matches_as_found")

    __table_args__ = (db.UniqueConstraint("lost_item_id", "found_item_id", name="uq_item_match_pair"),)
