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


@pytest.fixture(autouse=True)
def _clear_token_cache():
    auth._valid_token_cache.clear()
    yield
    auth._valid_token_cache.clear()


@pytest.fixture
def forged_cookie_client():
    """Client with a cookie that ChurchTools does not accept."""
    app.dependency_overrides[get_http_client] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: MagicMock()
    with patch("app.services.auth.validate_login_token", AsyncMock(return_value=False)):
        yield TestClient(app, cookies={settings.cookie_session: "forged", "csrf_token": "t"}, follow_redirects=False)
    app.dependency_overrides.clear()


@pytest.mark.real_token_validation
def test_forged_cookie_cannot_upload_logo(forged_cookie_client):
    with patch("app.api.images.save_logo") as save_logo:
        response = forged_cookie_client.post(
            "/logo/upload", files={"file": ("logo.png", _png_bytes(), "image/png")}, headers={"X-CSRF-Token": "t"}
        )
    assert response.status_code == 401
    save_logo.assert_not_called()


@pytest.mark.real_token_validation
def test_forged_cookie_cannot_delete_background(forged_cookie_client):
    with patch("app.api.images.delete_background_image") as delete_bg:
        response = forged_cookie_client.delete("/background", headers={"X-CSRF-Token": "t"})
    assert response.status_code == 401
    delete_bg.assert_not_called()


@pytest.mark.real_token_validation
def test_forged_cookie_cannot_read_logo(forged_cookie_client):
    assert forged_cookie_client.get("/logo").status_code == 401


@pytest.mark.real_token_validation
def test_forged_cookie_on_page_redirects_and_clears_cookie(forged_cookie_client):
    response = forged_cookie_client.get("/profile")
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert f'{settings.cookie_session}=""' in response.headers["set-cookie"]


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
