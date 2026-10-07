from app.extensions import db
from app.models.audit_log import AuditLog


def record_admin_action(actor, action, target_type, target_id, summary):
    db.session.add(AuditLog(actor_id=actor.id, action=action, target_type=target_type,
                            target_id=target_id, summary=summary))
