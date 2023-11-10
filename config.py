import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    CHURCHTOOLS_BASE = os.getenv('CHURCHTOOLS_BASE', '<SET CHURCHTOOLS_BASE IN .ENV FILE>')
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', f'{CHURCHTOOLS_BASE}-tpjOUrHAAcbJtDxNCgM5St7SWmEs0kmAJ5htjiqL')
    CHURCHTOOLS_BASE_URL = os.getenv('CHURCHTOOLS_BASE_URL', f"https://{CHURCHTOOLS_BASE}")
    FILE_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saved_files')
