from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import functools

bp = Blueprint('auth', __name__, template_folder='pages', url_prefix='')


@bp.route('/auth')
def home():
    return "Users Home Page."


@bp.route('/login', methods=['POST', 'GET'])
def login():
    from ..database import get_db
    from .dataclass import User
    db = get_db()

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        error = None

        row = db.execute('SELECT * FROM tbl_user WHERE username=?;', (username,)).fetchone()
        if not row:
            error = "User is not registered"
        else:
            user = User(db=db)
            user.get(username=username)
            if not check_password_hash(user.password, password):
                error = "Invalid password"

        if error is None:
            login_user(user)
            return redirect(url_for('home_page.home'))

        flash(error)
        return render_template('auth/login.html', username=username)

    return render_template('auth/login.html', username="")


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


def superuser_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role != 'superuser':
            from flask import abort
            abort(403)
        return view(**kwargs)
    return wrapped_view
