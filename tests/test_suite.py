import pytest
import sys
import os

# Add the main directory to the Python path so that modules can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# We use pytest instead of unittest for the test suite because it handles asyncio better
if __name__ == '__main__':
    # Run all tests with pytest
    sys.exit(pytest.main(["-v", "tests/"]))