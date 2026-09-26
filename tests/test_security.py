"""Login token validation and image upload hardening."""

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.database import get_db
from app.dependencies import get_http_client
from app.main import app
from app.services import auth


def _whoami_response(status_code=200, person_id=42):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {"data": {"id": person_id}}
    return response


def _png_bytes(size=(10, 10)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "red").save(buffer, "PNG")
    return buffer.getvalue()


SVG_WITH_SCRIPT = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


@pytest.fixture(autouse=True)
def _clear_token_cache():
    auth._valid_token_cache.clear()
    yield
    auth._valid_token_cache.clear()


# --- validate_login_token ---------------------------------------------------


@pytest.mark.real_token_validation
async def test_token_valid_for_real_person():
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=42)
    assert await auth.validate_login_token("good", client) is True


@pytest.mark.real_token_validation
async def test_token_invalid_when_churchtools_returns_anonymous_user():
    # ChurchTools answers invalid tokens with HTTP 200 and the anonymous user (id -1).
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=-1)
    assert await auth.validate_login_token("bogus", client) is False


@pytest.mark.real_token_validation
async def test_token_invalid_on_401():
    client = AsyncMock()
    client.get.return_value = _whoami_response(status_code=401)
    assert await auth.validate_login_token("expired", client) is False


@pytest.mark.real_token_validation
async def test_valid_token_is_cached():
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=42)
    await auth.validate_login_token("good", client)
    await auth.validate_login_token("good", client)
    assert client.get.call_count == 1


@pytest.mark.real_token_validation
async def test_invalid_token_is_not_cached():
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=-1)
    await auth.validate_login_token("bogus", client)
    await auth.validate_login_token("bogus", client)
    assert client.get.call_count == 2


# --- routes reject forged cookies ---------------------------------------------


@pytest.fixture
def forged_cookie_client():
    """Client with a cookie that ChurchTools does not accept."""
    app.dependency_overrides[get_http_client] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    with patch("app.services.auth.validate_login_token", AsyncMock(return_value=False)):
        yield TestClient(
            app, cookies={settings.cookie_login_token: "forged", "csrf_token": "t"}, follow_redirects=False
        )
    app.dependency_overrides.clear()


@pytest.mark.real_token_validation
def test_forged_cookie_cannot_upload_logo(forged_cookie_client):
    with patch("app.api.appointments.save_logo") as save_logo:
        response = forged_cookie_client.post(
            "/logo/upload", files={"file": ("logo.png", _png_bytes(), "image/png")}, headers={"X-CSRF-Token": "t"}
        )
    assert response.status_code == 401
    save_logo.assert_not_called()


@pytest.mark.real_token_validation
def test_forged_cookie_cannot_delete_background(forged_cookie_client):
    with patch("app.api.appointments.delete_background_image") as delete_bg:
        response = forged_cookie_client.delete("/background", headers={"X-CSRF-Token": "t"})
    assert response.status_code == 401
    delete_bg.assert_not_called()


@pytest.mark.real_token_validation
def test_forged_cookie_cannot_read_logo(forged_cookie_client):
    assert forged_cookie_client.get("/logo").status_code == 401


@pytest.mark.real_token_validation
def test_forged_cookie_on_overview_redirects_and_clears_cookie(forged_cookie_client):
    response = forged_cookie_client.get("/overview")
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert f'{settings.cookie_login_token}=""' in response.headers["set-cookie"]


@pytest.mark.real_token_validation
def test_forged_cookie_cannot_generate(forged_cookie_client):
    body = {
        "type": "pdf",
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "calendar_ids": ["1"],
        "appointment_ids": ["1_1"],
        "color_settings": {"name": "default"},
        "additional_infos": {"1_1": "injected"},
    }
    with patch("app.api.appointments.save_additional_infos") as save_infos:
        response = forged_cookie_client.post("/api/generate", json=body, headers={"X-CSRF-Token": "t"})
    assert response.status_code == 401
    save_infos.assert_not_called()


# --- image uploads --------------------------------------------------------------


@pytest.fixture
def authed_client():
    app.dependency_overrides[get_http_client] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app, cookies={settings.cookie_login_token: "token", "csrf_token": "t"})
    app.dependency_overrides.clear()


def _upload(client, content, filename="logo.png", content_type="image/png"):
    return client.post("/logo/upload", files={"file": (filename, content, content_type)}, headers={"X-CSRF-Token": "t"})


def test_png_upload_is_accepted(authed_client):
    with patch("app.api.appointments.save_logo") as save_logo:
        response = _upload(authed_client, _png_bytes())
    assert response.status_code == 200
    save_logo.assert_called_once()


def test_svg_upload_is_rejected(authed_client):
    with patch("app.api.appointments.save_logo") as save_logo:
        response = _upload(authed_client, SVG_WITH_SCRIPT, "logo.svg", "image/svg+xml")
    assert response.status_code == 400
    save_logo.assert_not_called()


def test_non_image_with_png_extension_is_rejected(authed_client):
    with patch("app.api.appointments.save_logo") as save_logo:
        response = _upload(authed_client, b"<html><script>alert(1)</script></html>")
    assert response.status_code == 400
    save_logo.assert_not_called()


def test_gif_upload_is_rejected(authed_client):
    buffer = BytesIO()
    Image.new("RGB", (5, 5)).save(buffer, "GIF")
    with patch("app.api.appointments.save_logo") as save_logo:
        response = _upload(authed_client, buffer.getvalue(), "logo.gif", "image/gif")
    assert response.status_code == 400
    save_logo.assert_not_called()


def test_oversized_image_dimensions_are_rejected(authed_client):
    with (
        patch("app.api.appointments.MAX_IMAGE_PIXELS", 50),
        patch("app.api.appointments.save_logo") as save_logo,
    ):
        response = _upload(authed_client, _png_bytes(size=(10, 10)))
    assert response.status_code == 413
    save_logo.assert_not_called()


def test_logo_content_type_comes_from_data_not_filename(authed_client):
    with patch("app.api.appointments.load_logo", return_value=(_png_bytes(), "logo.svg")):
        response = authed_client.get("/logo")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-security-policy"] == "default-src 'none'"


def test_legacy_svg_logo_is_not_served(authed_client):
    with patch("app.api.appointments.load_logo", return_value=(SVG_WITH_SCRIPT, "logo.svg")):
        response = authed_client.get("/logo")
    assert response.status_code == 404
