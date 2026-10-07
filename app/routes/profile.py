from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import ChangePasswordForm, ProfileForm
from app.models.claim import Claim
from app.models.item import Item

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


@profile_bp.get("/")
@login_required
def view_profile():
    lost_count = Item.query.filter_by(user_id=current_user.id, type="LOST").count()
    found_count = Item.query.filter_by(user_id=current_user.id, type="FOUND").count()
    returned_count = Item.query.filter_by(user_id=current_user.id, status="RETURNED").count()
    active_claim_count = Claim.query.filter_by(claimant_id=current_user.id, status="PENDING").count()
    recent_items = Item.query.filter_by(user_id=current_user.id).order_by(Item.created_at.desc()).limit(5).all()
    return render_template("profile/view.html", lost_count=lost_count, found_count=found_count,
                           returned_count=returned_count, active_claim_count=active_claim_count,
                           recent_items=recent_items)


@profile_bp.get("/items/<kind>")
@login_required
def my_items(kind):
    item_type = kind.upper()
    if item_type not in {"LOST", "FOUND"}:
        abort(404)
    items = Item.query.filter_by(user_id=current_user.id, type=item_type).order_by(Item.created_at.desc()).all()
    return render_template("profile/items.html", items=items, kind=item_type)


@profile_bp.get("/claims")
@login_required
def my_claims():
    claims = Claim.query.filter_by(claimant_id=current_user.id).order_by(Claim.created_at.desc()).all()
    return render_template("profile/claims.html", claims=claims)


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = ProfileForm(current_user.username, obj=current_user)
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        current_user.username = form.username.data.strip()
        db.session.commit()
        flash("Your profile has been updated.", "success")
        return redirect(url_for("profile.view_profile"))
    return render_template("profile/edit.html", form=form)


@profile_bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("That password doesn’t match your current password.")
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("Your password has been changed.", "success")
            return redirect(url_for("profile.view_profile"))
    return render_template("profile/password.html", form=form)
