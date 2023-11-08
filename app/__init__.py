from flask import Flask
import os


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object('config.Config')

    os.makedirs(app.config['FILE_DIRECTORY'], exist_ok=True)

    with app.app_context():
            # Include our Routes
            from . import views

            # Register Blueprints
            app.register_blueprint(views.main_bp)

            return app
