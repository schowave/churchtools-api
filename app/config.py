import os
import re
from pathlib import Path

# Read version from build-and-push-docker-image.sh
def get_version_from_script():
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'build-and-push-docker-image.sh')
        with open(script_path, 'r') as file:
            content = file.read()
            match = re.search(r'VERSION=(\d+\.\d+\.\d+)', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Error reading version: {e}")
    return "0.0.0"  # Fallback version

class Config:
    VERSION = get_version_from_script()
    CHURCHTOOLS_BASE = os.getenv('CHURCHTOOLS_BASE', '<SET CHURCHTOOLS_BASE IN .ENV FILE>')
    DB_PATH = os.getenv('DB_PATH', '<SET DB_PATH IN .ENV FILE>')
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', f'{CHURCHTOOLS_BASE}-tpjOUrHAAcbJtDxNCgM5St7SWmEs0kmAJ5htjiqL')
    CHURCHTOOLS_BASE_URL = os.getenv('CHURCHTOOLS_BASE_URL', f"https://{CHURCHTOOLS_BASE}")
    FILE_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saved_files')
    
    # Make sure the directory exists
    Path(FILE_DIRECTORY).mkdir(parents=True, exist_ok=True)