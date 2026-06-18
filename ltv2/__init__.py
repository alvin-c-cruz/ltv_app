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

    from ltv2.blueprints.main import bp as main_bp
    app.register_blueprint(main_bp)

    # Stub user_loader — replaced in Task 2 when the User model is added.
    @login_manager.user_loader
    def load_user(user_id):  # noqa: F841
        return None

    return app
