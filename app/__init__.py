from flask import Flask
import os
import sqlite3

from config import Config


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


def create_schema():
    db_path = Config.DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    sql = '''
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY,
        additional_info TEXT
    )
    '''
    try:
        cursor.execute(sql)
        conn.commit()
    except sqlite3.Error as e:
        print(f"An error occured: {e}")
    finally:
        conn.close()
