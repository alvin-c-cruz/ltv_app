from flask import Blueprint, render_template, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash

from ..auth import superuser_required
from ..database import get_db

bp = Blueprint('users', __name__, template_folder='pages', url_prefix='/users')

ROLES = ['staff', 'superuser']


def _all_users(db):
    return db.execute(
        "SELECT id, username, email, role, level FROM tbl_user ORDER BY username"
    ).fetchall()


def _get_user(db, user_id):
    return db.execute(
        "SELECT id, username, email, role, level FROM tbl_user WHERE id=?", (user_id,)
    ).fetchone()


def _username_taken(db, username, exclude_id=None):
    if exclude_id:
        row = db.execute(
            "SELECT id FROM tbl_user WHERE username=? AND id!=?", (username, exclude_id)
        ).fetchone()
    else:
        row = db.execute(
            "SELECT id FROM tbl_user WHERE username=?", (username,)
        ).fetchone()
    return row is not None


@bp.route('/')
@superuser_required
def home():
    db = get_db()
    users = [dict(u) for u in _all_users(db)]
    return render_template('users/home.html', users=users)


@bp.route('/add', methods=['GET', 'POST'])
@superuser_required
def add():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm', '')
        role     = request.form.get('role', 'staff')

        error = None
        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif _username_taken(get_db(), username):
            error = f'Username "{username}" is already taken.'

        if error:
            flash(error)
            form = dict(username=username, email=email, role=role)
            return render_template('users/add.html', form=form, roles=ROLES)

        db = get_db()
        db.execute(
            "INSERT INTO tbl_user (username, email, password, role, level) VALUES (?,?,?,?,?)",
            (username, email, generate_password_hash(password), role, 5)
        )
        db.commit()
        flash(f'User "{username}" created.')
        return redirect(url_for('users.home'))

    form = dict(username='', email='', role='staff')
    return render_template('users/add.html', form=form, roles=ROLES)


@bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@superuser_required
def edit(user_id):
    db = get_db()
    row = _get_user(db, user_id)
    if not row:
        flash('User not found.')
        return redirect(url_for('users.home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        role     = request.form.get('role', 'staff')

        error = None
        if not username:
            error = 'Username is required.'
        elif _username_taken(db, username, exclude_id=user_id):
            error = f'Username "{username}" is already taken.'

        if error:
            flash(error)
            form = dict(id=user_id, username=username, email=email, role=role)
            return render_template('users/edit.html', form=form, roles=ROLES)

        db.execute(
            "UPDATE tbl_user SET username=?, email=?, role=? WHERE id=?",
            (username, email, role, user_id)
        )
        db.commit()
        flash(f'User "{username}" updated.')
        return redirect(url_for('users.home'))

    form = dict(id=user_id, username=row['username'], email=row['email'] or '', role=row['role'])
    return render_template('users/edit.html', form=form, roles=ROLES)


@bp.route('/<int:user_id>/change-password', methods=['GET', 'POST'])
@superuser_required
def change_password(user_id):
    db = get_db()
    row = _get_user(db, user_id)
    if not row:
        flash('User not found.')
        return redirect(url_for('users.home'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm', '')

        error = None
        if not password:
            error = 'Password is required.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif password != confirm:
            error = 'Passwords do not match.'

        if error:
            flash(error)
            return render_template('users/change_password.html', user=dict(row))

        db.execute(
            "UPDATE tbl_user SET password=? WHERE id=?",
            (generate_password_hash(password), user_id)
        )
        db.commit()
        flash(f'Password updated for "{row["username"]}".')
        return redirect(url_for('users.home'))

    return render_template('users/change_password.html', user=dict(row))


@bp.route('/<int:user_id>/delete')
@superuser_required
def delete(user_id):
    from flask_login import current_user
    db = get_db()
    row = _get_user(db, user_id)
    if not row:
        flash('User not found.')
        return redirect(url_for('users.home'))

    if row['id'] == current_user.id:
        flash('You cannot delete your own account.')
        return redirect(url_for('users.home'))

    db.execute("DELETE FROM tbl_user WHERE id=?", (user_id,))
    db.commit()
    flash(f'User "{row["username"]}" deleted.')
    return redirect(url_for('users.home'))
