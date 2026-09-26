import os
import sys

# Add the main directory to the Python path so that modules can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402

from app.config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def _accept_login_tokens(request):
    """Treat every login token as valid unless a test opts out with @pytest.mark.real_token_validation."""
    if request.node.get_closest_marker("real_token_validation"):
        yield
        return
    with patch("app.services.auth.validate_login_token", AsyncMock(return_value=True)):
        yield


@pytest.fixture(autouse=True)
def _in_memory_sessions(request):
    """Treat the session cookie value as the ChurchTools token unless a test opts out with
    @pytest.mark.real_sessions (which then provides its own session database)."""
    if request.node.get_closest_marker("real_sessions"):
        yield
        return
    with (
        patch("app.services.sessions.get_session_token", side_effect=lambda session_id: session_id),
        patch("app.services.sessions.create_session", side_effect=lambda login_token: login_token),
        patch("app.services.sessions.delete_session"),
        patch("app.services.sessions.get_session_expiry", return_value=None),
        patch("app.services.sessions.purge_expired_sessions"),
    ):
        yield


@pytest.fixture
def config_mock():
    values = {"CHURCHTOOLS_BASE": "test.church.tools", "CHURCHTOOLS_BASE_URL": "https://test.church.tools"}
    with (
        patch.object(settings, "churchtools_base", values["CHURCHTOOLS_BASE"]),
        patch.object(settings, "churchtools_base_url", values["CHURCHTOOLS_BASE_URL"]),
        patch.object(settings, "version", "0.0.0-test"),
    ):
        yield values
