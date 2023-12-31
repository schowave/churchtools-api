from flask import Flask
import os
import sqlite3

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import Config


def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object('config.Config')

    os.makedirs(app.config['FILE_DIRECTORY'], exist_ok=True)

    pdfmetrics.registerFont(TTFont('Bahnschrift', 'Bahnschrift.ttf'))
    pdfmetrics.registerFont(TTFont('Bahnschrift-Bold', 'Bahnschrift.ttf'))

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
    sql_appointments = '''
    CREATE TABLE IF NOT EXISTS appointments (
        id TEXT PRIMARY KEY,
        additional_info TEXT
    )
    '''
    sql_color_settings = '''
    CREATE TABLE IF NOT EXISTS color_settings (
        setting_name TEXT PRIMARY KEY,
        background_color TEXT,
        background_alpha INTEGER,
        date_color TEXT,
        description_color TEXT
    )
    '''
    try:
        cursor.execute(sql_appointments)
        cursor.execute(sql_color_settings)
        conn.commit()
    except sqlite3.Error as e:
        print(f"An error occured: {e}")
    finally:
        conn.close()
