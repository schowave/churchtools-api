"""Render real templates end-to-end (no template mocks) to catch framework API changes."""

import re
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import get_http_client
from app.main import app
from app.schemas import ColorSettings

client = TestClient(app)
authed_client = TestClient(app, cookies={settings.cookie_session: "token"})


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


def test_pages_show_installed_version():
    login = client.get("/")
    overview = authed_client.get("/overview")
    for response in (login, overview):
        assert f'class="app-version" title="Installierte Version">v{settings.version}<' in response.text


def _render_appointments(has_images: bool) -> str:
    from app.database import get_db

    image = (b"\x89PNG\r\n\x1a\n", "x.png") if has_images else (None, None)
    app.dependency_overrides[get_db] = lambda: None
    with (
        patch("app.api.calendar_pages.fetch_calendars", AsyncMock(return_value=[])),
        patch("app.api.appointments.load_color_settings", return_value=ColorSettings()),
        patch("app.api.appointments.load_logo", return_value=image),
        patch("app.api.appointments.load_background_image", return_value=image),
    ):
        return authed_client.get("/appointments").text


def test_appointments_page_does_not_request_missing_images():
    html = _render_appointments(has_images=False)
    assert 'src="/logo"' not in html
    assert 'src="/background"' not in html


def test_appointments_page_shows_existing_images():
    html = _render_appointments(has_images=True)
    assert 'src="/logo"' in html
    assert 'src="/background"' in html


def test_pages_send_strict_content_security_policy():
    csp = client.get("/").headers["content-security-policy"]
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";") if d.strip())
    assert directives["script-src"] == "'self'"
    assert directives["object-src"] == "'none'"
    assert directives["frame-ancestors"] == "'none'"


def test_templates_contain_no_inline_scripts():
    from pathlib import Path

    for template in Path("app/templates").rglob("*.html"):
        html = template.read_text()
        inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html)
        assert not inline, f"inline <script> in {template}"
        assert not re.search(r"\son[a-z]+=", html), f"inline event handler in {template}"
