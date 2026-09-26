"""Render real templates end-to-end (no template mocks) to catch framework API changes."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import get_http_client
from app.main import app

client = TestClient(app)
authed_client = TestClient(app, cookies={settings.cookie_login_token: "token"})


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
    app.dependency_overrides[get_http_client] = lambda: AsyncMock()
    try:
        with patch("app.api.events.fetch_calendars", AsyncMock(return_value=calendars)):
            response = authed_client.get("/services")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
