# TODO: Create login layout

from flask import Blueprint, session, g, render_template, redirect, url_for, flash, request, current_app
import functools
import click
from flask.cli import with_appcontext
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('auth', __name__, template_folder='pages', url_prefix='')


@bp.route('/auth')
def home():
	return "Users Home Page."


@bp.route('/login', methods=['POST', 'GET'])
def login():
	from ..database import get_db
	from .dataclass import User
	db = get_db()
	user = User(db=db)

	if request.method == 'POST':
		username = request.form.get('username')
		password = request.form.get('password')
		error = None

		if not db.execute('SELECT username FROM tbl_user WHERE username=?;', (username, )).fetchone():
			error = "User is not registered"
		else:
			user.get(username=username)

			if not check_password_hash(user.password, password):
				error = "Invalid password"
		
		if error is None:
			session.clear()
			session['user_id'] = user.id
			return redirect(url_for('home_page.home'))

		flash(error)
	else:
		username = ""
		# Temporary auto-log
		# user.get(username='alvin')
		# session.clear()
		# session['user_id'] = user.id
		# return redirect(url_for('home_page.home'))

	return render_template('auth/login.html', username=username)


@bp.route('/logout')
def logout():
	session.clear()
	return redirect(url_for('auth.login'))


@bp.before_app_request
def load_logged_in_user():
	user_id = session.get('user_id')

	if user_id is None:
		g.user = None
	else:
		from .. database import get_db
		from .dataclass import User
		user = User(get_db())
		user.get(id=user_id)
		g.user = user


def login_required(view):
	@functools.wraps(view)
	def wrapped_view(**kwargs):
		if g.get('user') is None: return redirect(url_for('auth.login'))
		return view(**kwargs)
	return wrapped_view

