import os
import pytest
from app import create_app
from config import Config


class TestConfig(Config):
    """Test configuration that overrides the production configuration."""
    TESTING = True
    # Use a test database
    DB_PATH = 'test_database.db'
    # Use a fixed secret key for tests
    SECRET_KEY = 'test-secret-key'
    # Use a test directory for files
    FILE_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_files')


@pytest.fixture
def app():
    """Creates a test instance of the app."""
    app = create_app()
    app.config.from_object(TestConfig)
    
    # Ensure that the test directory exists
    os.makedirs(TestConfig.FILE_DIRECTORY, exist_ok=True)
    
    yield app
    
    # Cleanup: Delete test database if it exists
    if os.path.exists(TestConfig.DB_PATH):
        os.remove(TestConfig.DB_PATH)
    # Cleanup: Delete test files
    if os.path.exists(TestConfig.FILE_DIRECTORY):
        for file in os.listdir(TestConfig.FILE_DIRECTORY):
            os.remove(os.path.join(TestConfig.FILE_DIRECTORY, file))


@pytest.fixture
def client(app):
    """Creates a test client for the app."""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Creates an application context for the app."""
    with app.app_context() as context:
        yield context


@pytest.fixture
def request_context(app):
    """Creates a request context for the app."""
    with app.test_request_context() as context:
        yield context