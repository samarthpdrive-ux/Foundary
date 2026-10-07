from datetime import date
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms import ClaimForm, ItemReportForm, ITEM_CATEGORIES
from app.models.claim import Claim
from app.models.item import Item
from app.models.match import ItemMatch
from app.models.notification import Notification
from app.models.recovery_request import RecoveryRequest
from app.services.google_drive_storage import drive_image_url, image_file_id
from app.services.image_service import image_storage_options, remove_item_image, save_item_image
from app.services.matching import recalculate_for_item

items_bp = Blueprint("items", __name__)


def _upload_dir():
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _configure_claim_questions(form, item):
    form.verification_answer_1.label.text = item.verification_question_1 or "Share one identifying detail not shown in the listing"
    form.verification_answer_2.label.text = item.verification_question_2 or "Describe a mark, contents, or feature only the owner would know"
    form.verification_answer_3.label.text = item.verification_question_3 or "Add any other detail that can verify ownership"


def _populate_item(item, form, item_type):
    item.type = item_type
    item.title = form.title.data.strip()
    item.category = form.category.data
    item.description = form.description.data.strip()
    item.brand = (form.brand.data or "").strip() or None
    item.color = (form.color.data or "").strip() or None
    item.date = form.date.data
    item.time = form.time.data
    item.location_name = form.location_name.data.strip()
    item.latitude = form.latitude.data
    item.longitude = form.longitude.data
    item.share_exact_location = item_type == "LOST" and bool(form.share_exact_location.data)
    item.private_details = (form.private_details.data or "").strip() or None
    item.serial_number = (form.serial_number.data or "").strip() or None
    item.estimated_value = form.estimated_value.data
    item.additional_notes = (form.additional_notes.data or "").strip() or None
    item.storage_info = (form.storage_info.data or "").strip() or None
    item.verification_question_1 = (form.verification_question_1.data or "").strip() or None
    item.verification_question_2 = (form.verification_question_2.data or "").strip() or None
    item.verification_question_3 = (form.verification_question_3.data or "").strip() or None


@items_bp.route("/report/<item_type>", methods=["GET", "POST"])
@login_required
def create_report(item_type):
    item_type = item_type.upper()
    if item_type not in {"LOST", "FOUND"}:
        abort(404)
    form = ItemReportForm(item_type)
    form.submit.label.text = "Publish report"
    if form.validate_on_submit():
        if form.date.data > date.today():
            form.date.errors.append("The report date can’t be in the future.")
        else:
            try:
                image_name = save_item_image(form.image.data, _upload_dir(), **image_storage_options(current_app.config))
            except ValueError as error:
                form.image.errors.append(str(error))
            else:
                item = Item(user_id=current_user.id, status="ACTIVE")
                _populate_item(item, form, item_type)
                item.image_path = image_name
                db.session.add(item)
                db.session.flush()
                recalculate_for_item(item)
                db.session.commit()
                flash("Your report is published. We’ll surface possible matches as they appear.", "success")
                return redirect(url_for("items.detail", item_id=item.id))
    return render_template("items/report_form.html", form=form, item_type=item_type, editing=False)


@items_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_report(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id != current_user.id:
        abort(403)
    form = ItemReportForm(item.type, obj=item)
    form.submit.label.text = "Save changes"
    if form.validate_on_submit():
        if form.date.data > date.today():
            form.date.errors.append("The report date can’t be in the future.")
        else:
            old_image = item.image_path
            try:
                new_image = save_item_image(form.image.data, _upload_dir(), **image_storage_options(current_app.config))
            except ValueError as error:
                form.image.errors.append(str(error))
            else:
                _populate_item(item, form, item.type)
                if new_image:
                    item.image_path = new_image
                recalculate_for_item(item)
                db.session.commit()
                if new_image and old_image:
                    remove_item_image(old_image, _upload_dir(), **image_storage_options(current_app.config))
                flash("Your report has been updated.", "success")
                return redirect(url_for("items.detail", item_id=item.id))
    return render_template("items/report_form.html", form=form, item_type=item.type, editing=True, item=item)


@items_bp.post("/items/<int:item_id>/close")
@login_required
def close_report(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id != current_user.id:
        abort(403)
    if item.status not in {"RETURNED", "CLOSED"}:
        item.status = "CLOSED"
        for claim in Claim.query.filter_by(item_id=item.id, status="PENDING").all():
            claim.status = "REJECTED"
            db.session.add(Notification(user_id=claim.claimant_id, title="Claim update",
                                        message=f"The report for {item.title} has been closed.",
                                        type="CLAIM", related_item_id=item.id))
        for match in ItemMatch.query.filter(or_(ItemMatch.lost_item_id == item.id, ItemMatch.found_item_id == item.id)).all():
            match.status = "CLOSED"
        db.session.commit()
        flash("This report is now closed.", "success")
    return redirect(url_for("items.detail", item_id=item.id))


@items_bp.get("/uploads/<path:filename>")
def uploaded_image(filename):
    if filename.startswith("gdrive:"):
        file_id = image_file_id(filename)
        if not file_id or current_app.config.get("IMAGE_STORAGE_BACKEND") != "google_drive":
            abort(404)
        return redirect(drive_image_url(file_id), code=302)
    return send_from_directory(_upload_dir(), filename, max_age=3600)


@items_bp.get("/items")
def index():
    query = Item.query
    selected_type = request.args.get("type", "ALL").upper()
    if selected_type not in {"ALL", "LOST", "FOUND"}:
        selected_type = "ALL"
    if selected_type != "ALL":
        query = query.filter_by(type=selected_type)
    search = request.args.get("q", "").strip()[:100]
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Item.title.ilike(pattern), Item.category.ilike(pattern), Item.description.ilike(pattern), Item.brand.ilike(pattern), Item.color.ilike(pattern), Item.location_name.ilike(pattern)))
    category = request.args.get("category", "").strip()
    if category in {value for value, _ in ITEM_CATEGORIES}:
        query = query.filter_by(category=category)
    location = request.args.get("location", "").strip()[:100]
    color = request.args.get("color", "").strip()[:50]
    brand = request.args.get("brand", "").strip()[:80]
    if location:
        query = query.filter(Item.location_name.ilike(f"%{location}%"))
    if color:
        query = query.filter(Item.color.ilike(f"%{color}%"))
    if brand:
        query = query.filter(Item.brand.ilike(f"%{brand}%"))
    status = request.args.get("status", "ACTIVE").upper()
    if status in {"ACTIVE", "MATCHED", "CLAIMED", "RETURNED", "CLOSED"}:
        query = query.filter_by(status=status)
    elif status != "ALL":
        status = "ACTIVE"
        query = query.filter_by(status=status)
    for param, operator in (("date_from", "from"), ("date_to", "to")):
        raw = request.args.get(param, "")
        if raw:
            try:
                parsed = date.fromisoformat(raw)
                query = query.filter(Item.date >= parsed if operator == "from" else Item.date <= parsed)
            except ValueError:
                pass
    pagination = query.order_by(Item.created_at.desc()).paginate(page=request.args.get("page", 1, type=int), per_page=12, error_out=False)
    return render_template("items/index.html", pagination=pagination, selected_type=selected_type,
                           categories=ITEM_CATEGORIES, filters={"q": search, "category": category,
                           "location": location, "color": color, "brand": brand,
                           "status": status, "date_from": request.args.get("date_from", ""),
                           "date_to": request.args.get("date_to", "")})


@items_bp.get("/items/<int:item_id>")
def detail(item_id):
    item = db.get_or_404(Item, item_id)
    match_rows = ItemMatch.query.filter(or_(ItemMatch.lost_item_id == item.id, ItemMatch.found_item_id == item.id)).order_by(ItemMatch.score.desc()).all()
    possible_matches = [((row.found_item if item.type == "LOST" else row.lost_item), row.score) for row in match_rows if row.status == "SUGGESTED"]
    owner_claims = []
    recovery_requests = []
    if current_user.is_authenticated and item.user_id == current_user.id:
        owner_claims = Claim.query.filter_by(item_id=item.id, status="PENDING").order_by(Claim.created_at.asc()).all()
        recovery_requests = RecoveryRequest.query.filter_by(item_id=item.id, is_resolved=False).order_by(RecoveryRequest.created_at.desc()).all()
    claim_form = ClaimForm()
    _configure_claim_questions(claim_form, item)
    return render_template("items/detail.html", item=item, possible_matches=possible_matches,
                           owner_claims=owner_claims, claim_form=claim_form,
                           recovery_requests=recovery_requests)


@items_bp.route("/items/<int:item_id>/claim", methods=["GET", "POST"])
@login_required
def submit_claim(item_id):
    item = db.get_or_404(Item, item_id)
    if item.type != "FOUND" or item.status != "ACTIVE":
        abort(404)
    if item.user_id == current_user.id:
        abort(403)
    form = ClaimForm()
    _configure_claim_questions(form, item)
    if form.validate_on_submit():
        claim = Claim.query.filter_by(item_id=item.id, claimant_id=current_user.id).first()
        if claim and claim.status == "PENDING":
            flash("Your claim is already under review.", "info")
            return redirect(url_for("items.detail", item_id=item.id))
        if claim is None:
            claim = Claim(item_id=item.id, claimant_id=current_user.id)
            db.session.add(claim)
        claim.message = form.message.data.strip()
        claim.verification_answer_1 = form.verification_answer_1.data.strip()
        claim.verification_answer_2 = form.verification_answer_2.data.strip()
        claim.verification_answer_3 = (form.verification_answer_3.data or "").strip() or None
        claim.status = "PENDING"
        db.session.add(Notification(user_id=item.user_id, title="A new ownership claim was submitted",
                                    message=f"Someone submitted a claim for {item.title}.",
                                    type="CLAIM", related_item_id=item.id))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("You already have a claim under review for this item.", "info")
            return redirect(url_for("items.detail", item_id=item.id))
        flash("Your claim was sent to the finder for review.", "success")
        return redirect(url_for("profile.my_claims"))
    return render_template("items/claim_form.html", form=form, item=item)


@items_bp.post("/claims/<int:claim_id>/<decision>")
@login_required
def decide_claim(claim_id, decision):
    if decision not in {"approve", "reject"}:
        abort(404)
    claim = db.get_or_404(Claim, claim_id)
    item = claim.item
    if item.user_id != current_user.id:
        abort(403)
    if claim.status != "PENDING" or item.type != "FOUND" or item.status != "ACTIVE":
        flash("This claim can no longer be reviewed.", "info")
        return redirect(url_for("items.detail", item_id=item.id))
    if decision == "approve":
        claim.status = "APPROVED"
        item.status = "RETURNED"
        for match in ItemMatch.query.filter(or_(ItemMatch.lost_item_id == item.id, ItemMatch.found_item_id == item.id)).all():
            match.status = "CLOSED"
        for other in Claim.query.filter(Claim.item_id == item.id, Claim.id != claim.id, Claim.status == "PENDING"):
            other.status = "REJECTED"
            db.session.add(Notification(user_id=other.claimant_id, title="Claim update",
                                        message=f"The item {item.title} has been returned to another claimant.",
                                        type="CLAIM", related_item_id=item.id))
        message = f"Your claim for {item.title} was approved."
        flash("Claim approved and item marked returned.", "success")
    else:
        claim.status = "REJECTED"
        message = f"Your claim for {item.title} was declined."
        flash("Claim declined.", "success")
    db.session.add(Notification(user_id=claim.claimant_id, title="Claim update", message=message,
                                type="CLAIM", related_item_id=item.id))
    db.session.commit()
    return redirect(url_for("items.detail", item_id=item.id))
