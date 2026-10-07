from collections import OrderedDict

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, func, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.forms import MessageForm
from app.models.item import Item
from app.models.message import Message
from app.models.notification import Notification
from app.models.user import User
from app.models.conversation_consent import ConversationConsent

messages_bp = Blueprint("messages", __name__, url_prefix="/messages")


@messages_bp.get("/")
@login_required
def inbox():
    participation = or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id)
    peer_id = case(
        (Message.sender_id == current_user.id, Message.receiver_id),
        else_=Message.sender_id,
    )
    latest_ids = db.session.query(func.max(Message.id).label("latest_id")).filter(
        Message.item_id.isnot(None), participation,
    ).group_by(peer_id, Message.item_id).subquery()
    messages = Message.query.join(latest_ids, Message.id == latest_ids.c.latest_id).options(
        joinedload(Message.sender), joinedload(Message.receiver), joinedload(Message.item),
    ).order_by(Message.created_at.desc()).all()
    unread_rows = db.session.query(
        peer_id.label("peer_id"), Message.item_id, func.count(Message.id),
    ).filter(
        Message.receiver_id == current_user.id,
        Message.is_read.is_(False),
        Message.item_id.isnot(None),
    ).group_by(peer_id, Message.item_id).all()
    unread_by_thread = {(row[0], row[1]): row[2] for row in unread_rows}
    threads = OrderedDict()
    for message in messages:
        peer_id = message.receiver_id if message.sender_id == current_user.id else message.sender_id
        key = (peer_id, message.item_id)
        if key not in threads:
            peer = message.receiver if message.sender_id == current_user.id else message.sender
            item = message.item
            threads[key] = {"peer": peer, "item": item, "latest": message,
                            "unread": unread_by_thread.get(key, 0)}
    return render_template("messages/inbox.html", threads=threads.values())


@messages_bp.route("/new/<int:item_id>", methods=["GET", "POST"])
@login_required
def start(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id == current_user.id or item.status != "ACTIVE":
        abort(404)
    form = MessageForm()
    if form.validate_on_submit():
        message = Message(sender_id=current_user.id, receiver_id=item.user_id,
                          item_id=item.id, message=form.message.data.strip())
        db.session.add(message)
        db.session.add(Notification(user_id=item.user_id, title="You have a new message",
                                   message=f"A member contacted you about {item.title}.",
                                   type="MESSAGE", related_item_id=item.id))
        db.session.commit()
        flash("Your message was sent privately.", "success")
        return redirect(url_for("messages.thread", peer_id=item.user_id, item_id=item.id))
    return render_template("messages/compose.html", form=form, item=item)


@messages_bp.route("/<int:peer_id>/<int:item_id>", methods=["GET", "POST"])
@login_required
def thread(peer_id, item_id):
    peer = db.get_or_404(User, peer_id)
    item = db.get_or_404(Item, item_id)
    if peer.id == current_user.id or item.user_id not in {peer.id, current_user.id}:
        abort(403)
    conversation_query = Message.query.filter(
        Message.item_id == item.id,
        or_((Message.sender_id == current_user.id) & (Message.receiver_id == peer.id),
            (Message.sender_id == peer.id) & (Message.receiver_id == current_user.id)),
    )
    form = MessageForm()
    if form.validate_on_submit():
        if not db.session.query(conversation_query.exists()).scalar():
            abort(404)
        message = Message(sender_id=current_user.id, receiver_id=peer.id,
                          item_id=item.id, message=form.message.data.strip())
        db.session.add(message)
        db.session.add(Notification(user_id=peer.id, title="You have a new message",
                                   message=f"A member sent you a message about {item.title}.",
                                   type="MESSAGE", related_item_id=item.id))
        db.session.commit()
        flash("Message sent.", "success")
        return redirect(url_for("messages.thread", peer_id=peer.id, item_id=item.id))
    before_id = request.args.get("before", type=int)
    history_query = conversation_query
    if before_id:
        history_query = history_query.filter(Message.id < before_id)
    history_page = history_query.order_by(Message.id.desc()).limit(101).all()
    if not history_page:
        abort(404)
    has_older = len(history_page) > 100
    conversation = history_page[:100]
    conversation.reverse()
    oldest_message_id = conversation[0].id
    changed = Message.query.filter(
        Message.item_id == item.id,
        Message.receiver_id == current_user.id,
        Message.sender_id == peer.id,
        Message.is_read.is_(False),
    ).update({Message.is_read: True}, synchronize_session=False)
    if changed:
        db.session.commit()
    current_consent = ConversationConsent.query.filter_by(
        user_id=current_user.id, peer_id=peer.id, item_id=item.id,
    ).first()
    peer_consent = ConversationConsent.query.filter_by(
        user_id=peer.id, peer_id=current_user.id, item_id=item.id, allowed=True,
    ).first() is not None
    return render_template("messages/thread.html", peer=peer, item=item,
                           conversation=conversation, form=form,
                           has_older=has_older, oldest_message_id=oldest_message_id,
                           current_allows_admin_review=bool(current_consent and current_consent.allowed),
                           peer_allows_admin_review=peer_consent)


@messages_bp.post("/<int:peer_id>/<int:item_id>/admin-access/<action>")
@login_required
def set_admin_review_consent(peer_id, item_id, action):
    if action not in {"allow", "revoke"}:
        abort(404)
    peer = db.get_or_404(User, peer_id)
    item = db.get_or_404(Item, item_id)
    if peer.id == current_user.id or item.user_id not in {peer.id, current_user.id}:
        abort(403)
    has_conversation = Message.query.filter(
        Message.item_id == item.id,
        or_((Message.sender_id == current_user.id) & (Message.receiver_id == peer.id),
            (Message.sender_id == peer.id) & (Message.receiver_id == current_user.id)),
    ).first() is not None
    if not has_conversation:
        abort(404)

    consent = ConversationConsent.query.filter_by(
        user_id=current_user.id, peer_id=peer.id, item_id=item.id,
    ).first()
    allowed = action == "allow"
    if consent is None:
        consent = ConversationConsent(user_id=current_user.id, peer_id=peer.id,
                                     item_id=item.id, allowed=allowed)
        db.session.add(consent)
    else:
        consent.allowed = allowed
    verb = "allowed" if allowed else "revoked"
    db.session.add(Notification(
        user_id=peer.id,
        title="Admin chat review permission changed",
        message=f"@{current_user.username} {verb} admin review of your conversation about {item.title}. If either participant allows review, admins can read the full conversation.",
        type="MESSAGE", related_item_id=item.id,
    ))
    db.session.commit()
    flash(f"Admin review permission {verb} for this conversation.", "success")
    return redirect(url_for("messages.thread", peer_id=peer.id, item_id=item.id))
