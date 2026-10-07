from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import or_

from app.extensions import db, limiter
from app.forms import LoginForm, RegistrationForm
from app.models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_redirect_target(target):
    if not target:
        return None
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    if test.scheme in {"http", "https"} and ref.netloc == test.netloc:
        return target
    return None


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("profile.view_profile"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            full_name=form.full_name.data.strip(),
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Your account is ready. Welcome to Foundry.", "success")
        return redirect(url_for("profile.view_profile"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute; 50 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("profile.view_profile"))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter(or_(User.email == email, User.username == form.email.data.strip())).first()
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=False, fresh=True)
            flash("You’re signed in.", "success")
            return redirect(_safe_redirect_target(request.args.get("next")) or url_for("profile.view_profile"))
        flash("We couldn’t sign you in with those details.", "error")
    return render_template("auth/login.html", form=form)


@auth_bp.post("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("You’ve been signed out.", "success")
    return redirect(url_for("main.home"))
