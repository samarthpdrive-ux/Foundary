from datetime import UTC, datetime

from app.extensions import db


class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = db.Column(db.String(8), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(60), nullable=False)
    description = db.Column(db.Text, nullable=False)
    brand = db.Column(db.String(80))
    color = db.Column(db.String(50))
    private_details = db.Column(db.Text)
    serial_number = db.Column(db.String(120))
    estimated_value = db.Column(db.Numeric(10, 2))
    additional_notes = db.Column(db.Text)
    storage_info = db.Column(db.Text)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time)
    location_name = db.Column(db.String(160), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    share_exact_location = db.Column(db.Boolean, nullable=False, default=False)
    image_path = db.Column(db.String(255))
    verification_question_1 = db.Column(db.String(180))
    verification_question_2 = db.Column(db.String(180))
    verification_question_3 = db.Column(db.String(180))
    recovery_token = db.Column(db.String(64), unique=True, index=True)
    status = db.Column(db.String(16), nullable=False, default="ACTIVE", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    owner = db.relationship("User", back_populates="items")
    claims = db.relationship("Claim", back_populates="item", cascade="all, delete-orphan")
    recovery_requests = db.relationship("RecoveryRequest", back_populates="item", cascade="all, delete-orphan")
    messages = db.relationship("Message", back_populates="item")
    notifications = db.relationship("Notification", back_populates="related_item")
    reports = db.relationship("Report", back_populates="item")
    matches_as_lost = db.relationship("ItemMatch", foreign_keys="ItemMatch.lost_item_id", back_populates="lost_item", cascade="all, delete-orphan")
    matches_as_found = db.relationship("ItemMatch", foreign_keys="ItemMatch.found_item_id", back_populates="found_item", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint("type IN ('LOST', 'FOUND')", name="ck_items_type"),
        db.Index("ix_items_status_created", "status", "created_at"),
        db.Index("ix_items_type_status_created", "type", "status", "created_at"),
        db.Index("ix_items_category_status", "category", "status"),
    )
