from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.decorators import admin_required
from app.extensions import db
from app.forms import ITEM_CATEGORIES
from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.item import Item
from app.models.match import ItemMatch
from app.models.notification import Notification
from app.models.report import Report
from app.models.user import User
from app.models.conversation_consent import ConversationConsent
from app.models.message import Message
from app.services.audit import record_admin_action
from app.services.image_service import image_storage_options, remove_item_image
from app.services.matching import recalculate_for_item

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/")
@admin_required
def dashboard():
    stats = {
        "users": User.query.count(),
        "active_reports": Item.query.filter_by(status="ACTIVE").count(),
        "lost": Item.query.filter_by(type="LOST").count(),
        "found": Item.query.filter_by(type="FOUND").count(),
        "returned": Item.query.filter_by(status="RETURNED").count(),
        "pending_claims": Claim.query.filter_by(status="PENDING").count(),
        "open_reports": Report.query.filter_by(status="PENDING").count(),
    }
    latest_reports = Report.query.filter_by(status="PENDING").order_by(Report.created_at.desc()).limit(6).all()
    return render_template("admin/dashboard.html", stats=stats, latest_reports=latest_reports)


@admin_bp.get("/users")
@admin_required
def users():
    pagination = User.query.order_by(User.created_at.desc()).paginate(page=request.args.get("page", 1, type=int), per_page=30, error_out=False)
    return render_template("admin/users.html", pagination=pagination)


@admin_bp.post("/users/<int:user_id>/toggle")
@admin_required
def toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id or user.role == "ADMIN":
        abort(403)
    user.is_active = not user.is_active
    action = "ENABLE_USER" if user.is_active else "SUSPEND_USER"
    record_admin_action(current_user, action, "user", user.id, f"Account @{user.username} active={user.is_active}.")
    if not user.is_active:
        db.session.add(Notification(user_id=user.id, title="Account access changed",
                                    message="An administrator has disabled access to this account.", type="ACCOUNT"))
    db.session.commit()
    flash(f"Account @{user.username} is {'active' if user.is_active else 'disabled'}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.get("/items")
@admin_required
def items():
    pagination = Item.query.order_by(Item.created_at.desc()).paginate(page=request.args.get("page", 1, type=int), per_page=30, error_out=False)
    return render_template("admin/items.html", pagination=pagination)


@admin_bp.post("/items/<int:item_id>/close")
@admin_required
def close_item(item_id):
    item = db.get_or_404(Item, item_id)
    item.status = "CLOSED"
    for claim in Claim.query.filter_by(item_id=item.id, status="PENDING").all():
        claim.status = "REJECTED"
        db.session.add(Notification(user_id=claim.claimant_id, title="Claim update",
                                    message=f"The report for {item.title} has been closed.",
                                    type="CLAIM", related_item_id=item.id))
    for match in ItemMatch.query.filter((ItemMatch.lost_item_id == item.id) | (ItemMatch.found_item_id == item.id)).all():
        match.status = "CLOSED"
    record_admin_action(current_user, "HIDE_ITEM", "item", item.id, f"Closed report {item.title}.")
    db.session.add(Notification(user_id=item.user_id, title="Report status changed",
                                message=f"An administrator closed the report for {item.title}.",
                                type="REPORT", related_item_id=item.id))
    db.session.commit()
    flash("Report closed.", "success")
    return redirect(url_for("admin.items"))


@admin_bp.post("/items/<int:item_id>/reopen")
@admin_required
def reopen_item(item_id):
    item = db.get_or_404(Item, item_id)
    if item.status != "CLOSED":
        abort(400)
    item.status = "ACTIVE"
    recalculate_for_item(item)
    record_admin_action(current_user, "REOPEN_ITEM", "item", item.id, f"Reopened report {item.title}.")
    db.session.add(Notification(user_id=item.user_id, title="Report status changed",
                                message=f"An administrator reopened the report for {item.title}.",
                                type="REPORT", related_item_id=item.id))
    db.session.commit()
    flash("Report reopened.", "success")
    return redirect(url_for("admin.items"))


@admin_bp.post("/items/<int:item_id>/delete")
@admin_required
def delete_item(item_id):
    item = db.get_or_404(Item, item_id)
    record_admin_action(current_user, "DELETE_ITEM", "item", item.id, f"Deleted report {item.title}.")
    db.session.add(Notification(user_id=item.user_id, title="Report removed",
                                message="An administrator removed one of your reports.", type="REPORT"))
    remove_item_image(item.image_path, current_app.config["UPLOAD_FOLDER"], **image_storage_options(current_app.config))
    db.session.delete(item)
    db.session.commit()
    flash("Report deleted.", "success")
    return redirect(url_for("admin.items"))


@admin_bp.get("/claims")
@admin_required
def claims():
    pagination = Claim.query.order_by(Claim.created_at.desc()).paginate(page=request.args.get("page", 1, type=int), per_page=30, error_out=False)
    return render_template("admin/claims.html", pagination=pagination)


@admin_bp.post("/claims/<int:claim_id>/<decision>")
@admin_required
def decide_claim(claim_id, decision):
    if decision not in {"approve", "reject"}:
        abort(404)
    claim = db.get_or_404(Claim, claim_id)
    item = claim.item
    if claim.status != "PENDING" or item.status != "ACTIVE":
        flash("This claim is no longer pending.", "info")
        return redirect(url_for("admin.claims"))
    if decision == "approve":
        claim.status = "APPROVED"
        item.status = "RETURNED"
        for other in Claim.query.filter(Claim.item_id == item.id, Claim.id != claim.id, Claim.status == "PENDING"):
            other.status = "REJECTED"
            db.session.add(Notification(user_id=other.claimant_id, title="Claim update",
                                        message=f"The item {item.title} was returned to another claimant.",
                                        type="CLAIM", related_item_id=item.id))
        for match in ItemMatch.query.filter((ItemMatch.lost_item_id == item.id) | (ItemMatch.found_item_id == item.id)).all():
            match.status = "CLOSED"
        claim_message = f"Your claim for {item.title} was approved by a moderator."
        if item.user_id != claim.claimant_id:
            db.session.add(Notification(user_id=item.user_id, title="Item marked returned",
                                        message=f"A moderator approved a claim for {item.title}.",
                                        type="RETURNED", related_item_id=item.id))
        record_admin_action(current_user, "APPROVE_CLAIM", "claim", claim.id, f"Approved claim for {item.title}.")
    else:
        claim.status = "REJECTED"
        claim_message = f"Your claim for {item.title} was declined by a moderator."
        record_admin_action(current_user, "REJECT_CLAIM", "claim", claim.id, f"Rejected claim for {item.title}.")
    db.session.add(Notification(user_id=claim.claimant_id, title="Claim update", message=claim_message,
                                type="CLAIM", related_item_id=item.id))
    db.session.commit()
    flash("Claim decision recorded.", "success")
    return redirect(url_for("admin.claims"))


@admin_bp.get("/reports")
@admin_required
def reports():
    status = request.args.get("status", "PENDING").upper()
    query = Report.query
    if status != "ALL":
        status = status if status in {"PENDING", "RESOLVED"} else "PENDING"
        query = query.filter_by(status=status)
    pagination = query.order_by(Report.created_at.desc()).paginate(page=request.args.get("page", 1, type=int), per_page=30, error_out=False)
    return render_template("admin/reports.html", pagination=pagination, selected_status=status)


@admin_bp.post("/reports/<int:report_id>/<action>")
@admin_required
def review_report(report_id, action):
    if action not in {"dismiss", "warn", "hide", "delete", "suspend", "resolve"}:
        abort(404)
    report = db.get_or_404(Report, report_id)
    item = report.item
    target_user = report.reported_user or (item.owner if item else None)
    report.status = "RESOLVED"
    report.action_taken = action.upper()
    report.admin_note = request.form.get("admin_note", "").strip()[:2000] or None
    if action == "warn" and target_user:
        db.session.add(Notification(user_id=target_user.id, title="Community guidelines reminder",
                                    message="An administrator reviewed a report related to your account. Please follow the community guidelines.",
                                    type="ACCOUNT", related_item_id=item.id if item else None))
    elif action == "hide" and item:
        item.status = "CLOSED"
        for claim in Claim.query.filter_by(item_id=item.id, status="PENDING").all():
            claim.status = "REJECTED"
            db.session.add(Notification(user_id=claim.claimant_id, title="Claim update",
                                        message=f"The report for {item.title} has been closed.",
                                        type="CLAIM", related_item_id=item.id))
        for match in ItemMatch.query.filter((ItemMatch.lost_item_id == item.id) | (ItemMatch.found_item_id == item.id)).all():
            match.status = "CLOSED"
        db.session.add(Notification(user_id=item.user_id, title="Report status changed",
                                    message=f"An administrator hid the report for {item.title}.",
                                    type="REPORT", related_item_id=item.id))
    elif action == "delete" and item:
        remove_item_image(item.image_path, current_app.config["UPLOAD_FOLDER"], **image_storage_options(current_app.config))
        db.session.delete(item)
    elif action == "suspend" and target_user and target_user.role != "ADMIN":
        target_user.is_active = False
    record_admin_action(current_user, action.upper() + "_REPORT", "report", report.id,
                        f"Moderation action {action} on report #{report.id}.")
    if report.reporter_id:
        db.session.add(Notification(user_id=report.reporter_id, title="Moderation report reviewed",
                                    message="An administrator reviewed your report.", type="REPORT",
                                    related_item_id=item.id if item and action != "delete" else None))
    db.session.commit()
    flash("Moderation decision saved.", "success")
    return redirect(url_for("admin.reports"))


@admin_bp.get("/matches")
@admin_required
def matches():
    pagination = ItemMatch.query.order_by(ItemMatch.score.desc()).paginate(page=request.args.get("page", 1, type=int), per_page=30, error_out=False)
    return render_template("admin/matches.html", pagination=pagination)


@admin_bp.get("/categories")
@admin_required
def categories():
    return render_template("admin/categories.html", categories=[label for _, label in ITEM_CATEGORIES])


@admin_bp.get("/logs")
@admin_required
def logs():
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=request.args.get("page", 1, type=int), per_page=50, error_out=False)
    return render_template("admin/logs.html", pagination=pagination)


@admin_bp.get("/messages")
@admin_required
def messages():
    consents = ConversationConsent.query.filter_by(allowed=True).options(
        joinedload(ConversationConsent.user),
        joinedload(ConversationConsent.peer),
        joinedload(ConversationConsent.item),
    ).order_by(
        ConversationConsent.updated_at.desc()
    ).limit(200).all()
    conversations = {}
    for consent in consents:
        pair = tuple(sorted((consent.user_id, consent.peer_id)))
        key = (consent.item_id, pair)
        if key not in conversations:
            conversations[key] = {
                "item": consent.item,
                "users": (consent.user, consent.peer) if consent.user_id == pair[0] else (consent.peer, consent.user),
                "allowed_by": [],
            }
        conversations[key]["allowed_by"].append(consent.user.username)
    return render_template("admin/messages.html", conversations=conversations)


@admin_bp.get("/messages/<int:item_id>/<int:user_a_id>/<int:user_b_id>")
@admin_required
def view_conversation(item_id, user_a_id, user_b_id):
    if user_a_id == user_b_id:
        abort(404)
    user_a_id, user_b_id = sorted((user_a_id, user_b_id))
    consent_exists = ConversationConsent.query.filter(
        ConversationConsent.item_id == item_id,
        ConversationConsent.allowed.is_(True),
        or_(
            (ConversationConsent.user_id == user_a_id) & (ConversationConsent.peer_id == user_b_id),
            (ConversationConsent.user_id == user_b_id) & (ConversationConsent.peer_id == user_a_id),
        ),
    ).first()
    if consent_exists is None:
        abort(404)
    item = db.get_or_404(Item, item_id)
    users = User.query.filter(User.id.in_([user_a_id, user_b_id])).order_by(User.id.asc()).all()
    if len(users) != 2:
        abort(404)
    before_id = request.args.get("before", type=int)
    query = Message.query.filter(
        Message.item_id == item_id,
        or_((Message.sender_id == user_a_id) & (Message.receiver_id == user_b_id),
            (Message.sender_id == user_b_id) & (Message.receiver_id == user_a_id)),
    )
    if before_id:
        query = query.filter(Message.id < before_id)
    rows = query.order_by(Message.id.desc()).limit(101).all()
    if not rows:
        abort(404)
    has_older = len(rows) > 100
    conversation = rows[:100]
    conversation.reverse()
    record_admin_action(
        current_user, "VIEW_PRIVATE_MESSAGES", "conversation", item_id,
        f"Reviewed consent-enabled chat for item #{item_id} between users #{user_a_id} and #{user_b_id}.",
    )
    db.session.commit()
    return render_template(
        "admin/conversation.html", item=item, users=users, conversation=conversation,
        has_older=has_older, oldest_message_id=conversation[0].id,
        user_a_id=user_a_id, user_b_id=user_b_id,
    )
