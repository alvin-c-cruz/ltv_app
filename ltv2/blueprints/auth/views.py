from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from flask_login import login_user, logout_user, login_required, current_user
from ltv2.models.user import User

bp = Blueprint("auth", __name__)


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        from datetime import datetime, timedelta
        from flask import current_app
        from ltv2.extensions import db
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        now = datetime.utcnow()
        if user and user.locked_until and user.locked_until > now:
            flash("Account is locked. Try again later.", "error")
            return redirect(url_for("auth.login"))

        if user is None or not user.check_password(password):
            if user is not None:
                user.failed_logins = (user.failed_logins or 0) + 1
                if user.failed_logins >= current_app.config["MAX_FAILED_LOGINS"]:
                    user.locked_until = now + timedelta(
                        minutes=current_app.config["LOCKOUT_MINUTES"])
                db.session.commit()
            flash("Invalid username or password", "error")
            return redirect(url_for("auth.login"))

        user.failed_logins = 0
        user.locked_until = None
        db.session.commit()
        login_user(user)
        session.permanent = True
        return redirect(url_for("main.index"))
    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
