from datetime import UTC, datetime

from flask import current_app, has_app_context
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    profile_image = db.Column(db.String(255))
    role = db.Column(db.String(16), nullable=False, default="USER")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    items = db.relationship("Item", back_populates="owner", cascade="all, delete-orphan")
    claims = db.relationship("Claim", back_populates="claimant", cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        if self.role == "ADMIN":
            return True
        if has_app_context():
            configured_admin_email = current_app.config.get("ADMIN_EMAIL", "").strip().lower()
            return bool(configured_admin_email and self.email.strip().lower() == configured_admin_email)
        return False
