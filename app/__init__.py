from pathlib import Path

from flask import Flask
from flask_login import current_user
from config import Config
from app.extensions import csrf, db, limiter, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    if getattr(config_class, "validate", None):
        config_class.validate()
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Sign in to view that page."
    login_manager.login_message_category = "info"
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    from app.models import User  # noqa: F401
    from app.routes import admin_bp, auth_bp, items_bp, main_bp, maps_bp, messages_bp, moderation_bp, notifications_bp, profile_bp, recovery_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(maps_bp)
    app.register_blueprint(recovery_bp)
    app.register_blueprint(moderation_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def navigation_counts():
        if not current_user.is_authenticated:
            return {"unread_notifications": 0, "unread_messages": 0}
        from sqlalchemy import func, select
        from app.models.message import Message
        from app.models.notification import Notification
        counts = db.session.execute(select(
            select(func.count(Notification.id))
            .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
            .scalar_subquery(),
            select(func.count(Message.id))
            .where(Message.receiver_id == current_user.id, Message.is_read.is_(False))
            .scalar_subquery(),
        )).one()
        return {
            "unread_notifications": counts[0],
            "unread_messages": counts[1],
        }

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(self)")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(User, int(user_id))
            return user if user and user.is_active else None
        except (TypeError, ValueError):
            return None

    @app.cli.command("promote-admin")
    def promote_admin():
        """Promote the Render-configured admin account, or an explicitly selected account."""
        import click
        from app.models import User as Account
        email = app.config.get("ADMIN_EMAIL", "").strip().lower()
        if email:
            click.echo(f"Using ADMIN_EMAIL configured in this environment: {email}")
        else:
            click.echo("ADMIN_EMAIL is not configured; select an existing account interactively.")
            email = click.prompt("Existing account email").strip().lower()
        account = Account.query.filter_by(email=email).first()
        if not account:
            raise click.ClickException("No account with that email exists. Register that email first, then run this command again.")
        account.role = "ADMIN"
        db.session.commit()
        click.echo(f"{account.username} is now an administrator.")

    with app.app_context():
        if app.config.get("AUTO_CREATE_DB"):
            db.create_all()
            from app.services.schema_updates import add_missing_item_columns
            add_missing_item_columns(db.engine)

    return app
