from io import BytesIO
from secrets import token_urlsafe
from urllib.parse import urlsplit

import qrcode
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import RecoveryForm
from app.models.item import Item
from app.models.notification import Notification
from app.models.recovery_request import RecoveryRequest

recovery_bp = Blueprint("recovery", __name__)


def _safe_recovery_url(item):
    path = url_for("recovery.recover", token=item.recovery_token)
    base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    hostname = (urlsplit(base).hostname or "").lower() if base else ""
    local_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

    if current_app.debug and not base:
        base = request.url_root.rstrip("/")
    elif not base or hostname in local_hosts:
        raise RuntimeError(
            "Set PUBLIC_BASE_URL to the public HTTPS address before generating recovery QR codes."
        )

    return f"{base}{path}"


@recovery_bp.post("/items/<int:item_id>/qr/enable")
@login_required
def enable_qr(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id != current_user.id or item.status != "ACTIVE":
        abort(403)
    if not item.recovery_token:
        item.recovery_token = token_urlsafe(32)
        db.session.commit()
    flash("A private recovery QR link is ready.", "success")
    return redirect(url_for("items.detail", item_id=item.id))


@recovery_bp.post("/items/<int:item_id>/qr/disable")
@login_required
def disable_qr(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id != current_user.id:
        abort(403)
    item.recovery_token = None
    db.session.commit()
    flash("The recovery QR link has been disabled.", "success")
    return redirect(url_for("items.detail", item_id=item.id))


@recovery_bp.post("/recovery-requests/<int:request_id>/resolve")
@login_required
def resolve_request(request_id):
    recovery = db.get_or_404(RecoveryRequest, request_id)
    if recovery.item.user_id != current_user.id:
        abort(403)
    recovery.is_resolved = True
    db.session.commit()
    flash("Recovery note marked resolved.", "success")
    return redirect(url_for("items.detail", item_id=recovery.item_id))


@recovery_bp.get("/items/<int:item_id>/qr.png")
@login_required
def qr_image(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id != current_user.id:
        abort(403)
    if not item.recovery_token:
        abort(404)
    image = qrcode.make(_safe_recovery_url(item))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png", download_name=f"foundry-recovery-{item.id}.png")


@recovery_bp.route("/recover/<token>", methods=["GET", "POST"])
def recover(token):
    item = Item.query.filter_by(recovery_token=token, status="ACTIVE").first_or_404()
    form = RecoveryForm()
    if form.validate_on_submit():
        recovery = RecoveryRequest(item_id=item.id, message=form.message.data.strip(),
                                   contact_email=(form.contact_email.data or "").strip().lower() or None)
        db.session.add(recovery)
        db.session.add(Notification(user_id=item.user_id, title="Someone found your item",
                                   message=f"A finder sent a private recovery note about {item.title}.",
                                   type="RECOVERY", related_item_id=item.id))
        db.session.commit()
        return render_template("recovery/sent.html")
    return render_template("recovery/recover.html", item=item, form=form)
