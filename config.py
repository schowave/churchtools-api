import os

class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'evkila-tpjOUrHAAcbJtDxNCgM5St7SWmEs0kmAJ5htjiqL')
    CHURCHTOOLS_BASE_URL = os.getenv('CHURCHTOOLS_BASE_URL', 'https://evkila.church.tools')
    FILE_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saved_files')
