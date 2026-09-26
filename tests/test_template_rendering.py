"""Render real templates end-to-end (no template mocks) to catch framework API changes."""

import re
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import get_http_client
from app.main import app

client = TestClient(app)
authed_client = TestClient(app, cookies={settings.cookie_login_token: "token"})


def _form_token(html: str) -> str:
    return re.search(r'name="_csrf_token" value="([^"]*)"', html).group(1)


@pytest.fixture(autouse=True)
def _http_client_override():
    http_client = AsyncMock()
    http_client.post.return_value.status_code = 401
    app.dependency_overrides[get_http_client] = lambda: http_client
    yield
    app.dependency_overrides.clear()


def test_login_page_renders():
    response = client.get("/")
    assert response.status_code == 200
    assert "<form" in response.text


def test_overview_page_renders():
    response = authed_client.get("/overview")
    assert response.status_code == 200
    assert "Termin-Folien" in response.text


def test_services_page_renders():
    calendars = [{"id": 1, "name": "Gottesdienste", "isPublic": True}]
    with patch("app.api.calendar_pages.fetch_calendars", AsyncMock(return_value=calendars)):
        response = authed_client.get("/services")
    assert response.status_code == 200


def test_first_visit_login_form_carries_csrf_token():
    """A fresh browser (no csrf cookie yet) must get the same token in the form as in the cookie."""
    fresh = TestClient(app)
    response = fresh.get("/")
    cookie_token = response.cookies.get("csrf_token")
    assert cookie_token
    assert f'name="_csrf_token" value="{cookie_token}"' in response.text


def test_first_visit_login_succeeds_with_rendered_form_token():
    fresh = TestClient(app, follow_redirects=False)
    page = fresh.get("/")
    token = page.cookies.get("csrf_token")
    response = fresh.post("/", data={"username": "u", "password": "p", "_csrf_token": _form_token(page.text)})
    assert token
    # Passes CSRF and reaches the login handler (ChurchTools mock rejects the credentials).
    assert response.status_code == 200
    assert "ungültig" in response.text
    # The re-rendered form must carry the token again, so the retry is not blocked.
    assert _form_token(response.text) == token
