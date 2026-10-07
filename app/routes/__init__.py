from app.routes.auth import auth_bp
from app.routes.main import main_bp
from app.routes.profile import profile_bp
from app.routes.items import items_bp
from app.routes.messages import messages_bp
from app.routes.notifications import notifications_bp
from app.routes.maps import maps_bp
from app.routes.recovery import recovery_bp
from app.routes.admin import admin_bp
from app.routes.moderation import moderation_bp

__all__ = ["auth_bp", "main_bp", "profile_bp", "items_bp", "messages_bp", "notifications_bp", "maps_bp", "recovery_bp", "admin_bp", "moderation_bp"]
