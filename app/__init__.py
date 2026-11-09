import os

from flask import Flask

from .config import Config
from .extensions import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.setdefault("RECEIPT_DIR", os.path.join(app.instance_path, "receipts"))
    os.makedirs(app.config["RECEIPT_DIR"], exist_ok=True)

    db.init_app(app)

    @app.url_defaults
    def version_static(endpoint, values):
        """Cache-bust static files: url_for('static', ...) gets ?v=<last modified time>."""
        if endpoint == "static" and "filename" in values and "v" not in values:
            path = os.path.join(app.static_folder, values["filename"])
            if os.path.isfile(path):
                values["v"] = int(os.stat(path).st_mtime)

    from . import auth, claims, routes
    app.register_blueprint(auth.bp)
    app.register_blueprint(claims.bp)
    app.register_blueprint(routes.bp)

    with app.app_context():
        db.create_all()  # the blueprints above already imported the models, so every table is known
        if app.config["SEED_SAMPLE_DATA"]:
            from .seed import seed_if_empty
            seed_if_empty()

    return app
