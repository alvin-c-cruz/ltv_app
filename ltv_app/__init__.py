from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
import secrets


def _get_version():
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        # VERSION lives in the server/ root, one level up from ltv_app/
        version_file = os.path.normpath(os.path.join(base, '..', 'VERSION'))
        with open(version_file) as f:
            return f.read().strip()
    except Exception:
        return "4.0.0"


VERSION = _get_version()


def _ensure_instance_dirs(instance_path):
    """Create the instance subdirectories the app writes into but never creates.

    `instance/` is gitignored wholesale, so a fresh clone has none of these.
    `temp/` in particular is written to by the fixings, gain_loss, forecasts,
    block_unblock, notebook and trades_done exports.
    """
    for path in (instance_path,
                 os.path.join(instance_path, "test_database"),
                 os.path.join(instance_path, "temp")):
        os.makedirs(path, exist_ok=True)


def create_app(test_config=None):
    # instance/ (live DB, excel_templates, temp) sits beside this package, as a
    # sibling of ltv_app/ — matching PythonAnywhere's deployed tree, which is
    # flat the same way. Do not hardcode a deeper climb:
    # a wrong instance_path is created silently by _ensure_instance_dirs() below,
    # so the app boots against an empty database instead of failing loudly.
    _apps_dir = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    app = Flask(__name__, instance_path=os.path.join(_apps_dir, 'instance'),
                instance_relative_config=True)
    app.config.from_mapping(
        # Random per-process fallback so a fresh clone still boots without a
        # committed secret. Overridden below by instance/config.py (untracked).
        # NOTE: the app is built with instance_relative_config=True, so
        # from_pyfile('config.py') resolves against instance_path -- the file
        # must be at instance/config.py, NOT the server/ root.
        SECRET_KEY=secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "LTV Stocks.db"),
        # No CSRFProtect is registered, so SameSite is the only thing stopping a
        # cross-site state-changing POST. SESSION_COOKIE_SECURE is deliberately
        # left False here and set to True in PythonAnywhere's instance/config.py
        # -- setting it in code would break login over local plain HTTP.
        SESSION_COOKIE_SAMESITE="Lax",
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    _ensure_instance_dirs(app.instance_path)

    app.jinja_env.globals['app_version'] = VERSION

    from .tz import ph_now, ph_today
    app.jinja_env.globals['ph_now'] = ph_now
    app.jinja_env.globals['ph_today'] = ph_today

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from .blueprints.database.views import get_db
        from .blueprints.auth.dataclass import User
        user = User(db=get_db())
        user.get(id=int(user_id))
        return user if user.id else None

    from . import blueprints
    for module_ in dir(blueprints):
        module_obj = getattr(blueprints, module_)
        if hasattr(module_obj, 'bp'):
            app.register_blueprint(getattr(module_obj, 'bp'))

    return app
