"""Profile page: user data from ChurchTools, session validity, logout."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas import CurrentUser
from app.web import get_http_client

USER = CurrentUser(id=42, first_name="Erika", last_name="Muster", email="erika@example.org")


@pytest.fixture(autouse=True)
def _http_client_override():
    app.dependency_overrides[get_http_client] = lambda: AsyncMock()
    yield
    app.dependency_overrides.clear()


def _get_profile(**patches):
    client = TestClient(app, cookies={settings.cookie_session: "token"}, follow_redirects=False)
    with (
        patch("app.api.auth.fetch_current_user", AsyncMock(**patches)),
        patch("app.api.auth.sessions.get_session_expiry", return_value=datetime(2026, 10, 26, 7, 30)),
    ):
        return client.get("/profile")


def test_profile_refreshes_navigation_initials(config_mock):
    with patch("app.api.auth.sessions.set_session_display_name") as set_name:
        response = _get_profile(return_value=USER)

    set_name.assert_called_once_with("token", "Erika Muster")
    # The navigation shows the initials right away
    assert 'aria-label="Profil von Erika Muster"' in response.text


def test_profile_shows_user_and_session(config_mock):
    response = _get_profile(return_value=USER)

    assert response.status_code == 200
    html = response.text
    assert "Erika Muster" in html
    assert "erika<wbr>@example.org" in html  # may break before the "@" on phones
    assert "ChurchTools-ID 42" in html
    assert 'class="profile-avatar" aria-hidden="true">EM<' in html
    assert "26.10.2026" in html
    assert 'action="/logout"' in html
    assert f'href="{config_mock["CHURCHTOOLS_BASE_URL"]}"' in html


def test_profile_still_offers_logout_when_churchtools_fails(config_mock):
    response = _get_profile(side_effect=httpx2.ConnectError("down"))

    assert response.status_code == 200
    assert "konnten gerade nicht geladen werden" in response.text
    assert 'action="/logout"' in response.text


def test_profile_requires_login():
    response = TestClient(app, follow_redirects=False).get("/profile")

    assert response.status_code == 303
    assert response.headers["location"] == "/"
