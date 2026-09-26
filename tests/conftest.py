import os
import sys

# Add the main directory to the Python path so that modules can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _accept_login_tokens(request):
    """Treat every login token as valid unless a test opts out with @pytest.mark.real_token_validation."""
    if request.node.get_closest_marker("real_token_validation"):
        yield
        return
    with patch("app.services.auth.validate_login_token", AsyncMock(return_value=True)):
        yield
