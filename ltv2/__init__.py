import os
from flask import Flask
from ltv2.extensions import db, migrate, login_manager


def create_app(config_object="ltv2.config.DevConfig"):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)

    os.makedirs(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance"),
        exist_ok=True,
    )

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from ltv2 import models  # noqa: F401  (ensures models are registered)

    from ltv2.blueprints.main import bp as main_bp
    app.register_blueprint(main_bp)

    from ltv2.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from ltv2.blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from flask import session

    @app.before_request
    def _refresh_session():
        session.permanent = True
        session.modified = True

    return app
