from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.database import get_db
from app.main import app
from app.services import auth
from app.web import get_http_client


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


@pytest.fixture
def authed_client():
    app.dependency_overrides[get_http_client] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(app, cookies={settings.cookie_session: "token", "csrf_token": "t"})
    app.dependency_overrides.clear()


def _upload(client, content, filename="logo.png", content_type="image/png"):
    return client.post("/logo/upload", files={"file": (filename, content, content_type)}, headers={"X-CSRF-Token": "t"})


def test_png_upload_is_accepted(authed_client):
    with patch("app.api.images.save_logo") as save_logo:
        response = _upload(authed_client, _png_bytes())
    assert response.status_code == 200
    save_logo.assert_called_once()


def test_svg_upload_is_rejected(authed_client):
    with patch("app.api.images.save_logo") as save_logo:
        response = _upload(authed_client, SVG_WITH_SCRIPT, "logo.svg", "image/svg+xml")
    assert response.status_code == 400
    save_logo.assert_not_called()


def test_non_image_with_png_extension_is_rejected(authed_client):
    with patch("app.api.images.save_logo") as save_logo:
        response = _upload(authed_client, b"<html><script>alert(1)</script></html>")
    assert response.status_code == 400
    save_logo.assert_not_called()


def test_gif_upload_is_rejected(authed_client):
    buffer = BytesIO()
    Image.new("RGB", (5, 5)).save(buffer, "GIF")
    with patch("app.api.images.save_logo") as save_logo:
        response = _upload(authed_client, buffer.getvalue(), "logo.gif", "image/gif")
    assert response.status_code == 400
    save_logo.assert_not_called()


def test_oversized_image_dimensions_are_rejected(authed_client):
    with (
        patch("app.api.images.MAX_IMAGE_PIXELS", 50),
        patch("app.api.images.save_logo") as save_logo,
    ):
        response = _upload(authed_client, _png_bytes(size=(10, 10)))
    assert response.status_code == 413
    save_logo.assert_not_called()


def test_logo_content_type_comes_from_data_not_filename(authed_client):
    with patch("app.api.images.load_logo", return_value=(_png_bytes(), "logo.svg")):
        response = authed_client.get("/logo")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-security-policy"] == "default-src 'none'"


def test_legacy_svg_logo_is_not_served(authed_client):
    with patch("app.api.images.load_logo", return_value=(SVG_WITH_SCRIPT, "logo.svg")):
        response = authed_client.get("/logo")
    assert response.status_code == 404
