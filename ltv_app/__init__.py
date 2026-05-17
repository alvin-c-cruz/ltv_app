from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="acda5284c0cc9a93e828516b701ab77907cd9bfe5f4f00c5026059b2d7f58419",
        DATABASE=os.path.join("ltv_database", "LTV Stocks.db"),  # TODO: Use instance when migration is done
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
        os.makedirs(os.path.join(app.instance_path, "test_database"))
    except OSError:
        pass

    from . import blueprints
    for module_ in dir(blueprints):
        module_obj = getattr(blueprints, module_)
        if hasattr(module_obj, 'bp'):
            app.register_blueprint(getattr(module_obj, 'bp'))

    return app
