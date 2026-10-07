from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import ListingReportForm
from app.models.item import Item
from app.models.notification import Notification
from app.models.report import Report
from app.models.user import User

moderation_bp = Blueprint("moderation", __name__, url_prefix="/items")


@moderation_bp.route("/<int:item_id>/report", methods=["GET", "POST"])
@login_required
def report_listing(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id == current_user.id:
        abort(403)
    form = ListingReportForm()
    if form.validate_on_submit():
        report = Report(reporter_id=current_user.id, reported_user_id=item.user_id,
                        item_id=item.id, reason=form.reason.data,
                        description=form.description.data.strip())
        db.session.add(report)
        for admin in User.query.filter_by(role="ADMIN", is_active=True).all():
            db.session.add(Notification(user_id=admin.id, title="A listing needs review",
                                        message=f"A member reported {item.title}.", type="REPORT",
                                        related_item_id=item.id))
        db.session.commit()
        flash("Thanks. The moderation team has received your report.", "success")
        return redirect(url_for("items.detail", item_id=item.id))
    return render_template("moderation/report_form.html", form=form, item=item)
