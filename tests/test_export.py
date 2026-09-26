"""Export generation must not block the event loop and must use the configured timezone."""

import threading
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.dependencies import get_http_client
from app.main import app
from app.utils import export_timestamp


@pytest.fixture
def client():
    app.dependency_overrides[get_http_client] = lambda: AsyncMock()
    app.dependency_overrides[get_db] = lambda: None
    yield TestClient(app, cookies={settings.cookie_session: "token", "csrf_token": "t"})
    app.dependency_overrides.clear()


GENERATE_BODY = {
    "type": "jpeg",
    "start_date": "2026-09-27",
    "end_date": "2026-10-04",
    "calendar_ids": ["1"],
    "appointment_ids": ["1_1"],
    "color_settings": {"name": "default"},
}


def test_pdf_and_jpeg_generation_run_off_the_event_loop(client):
    threads = {}

    async def fake_fetch(*args, **kwargs):
        threads["loop"] = threading.get_ident()
        return []

    def fake_create_pdf(*args, **kwargs):
        threads["pdf"] = threading.get_ident()
        return b"%PDF"

    def fake_jpeg(pdf_bytes):
        threads["jpeg"] = threading.get_ident()
        return b"PK"

    with (
        patch("app.api.appointments.fetch_appointments", fake_fetch),
        patch("app.api.appointments.create_pdf", fake_create_pdf),
        patch("app.api.appointments.handle_jpeg_generation", fake_jpeg),
        patch("app.api.appointments.save_additional_infos"),
        patch("app.api.appointments.save_color_settings"),
        patch("app.api.appointments.load_logo", return_value=(None, None)),
        patch("app.api.appointments.load_background_image", return_value=(None, None)),
    ):
        response = client.post("/api/generate", json=GENERATE_BODY, headers={"X-CSRF-Token": "t"})

    assert response.status_code == 200
    assert threads["pdf"] != threads["loop"]
    assert threads["jpeg"] != threads["loop"]


def test_export_timestamp_uses_configured_timezone():
    utc_now = datetime(2026, 9, 27, 8, 0, 0, tzinfo=UTC)
    assert export_timestamp(utc_now, tz=ZoneInfo("Europe/Berlin")) == "2026-09-27-10-00-00"


def test_generate_ignores_client_supplied_profile(client):
    with (
        patch("app.api.appointments.fetch_appointments", AsyncMock(return_value=[])),
        patch("app.api.appointments.create_pdf", return_value=b"%PDF"),
        patch("app.api.appointments.save_additional_infos"),
        patch("app.api.appointments.save_color_settings"),
        patch("app.api.appointments.load_logo", return_value=(None, None)) as load_logo,
        patch("app.api.appointments.load_background_image", return_value=(None, None)) as load_bg,
    ):
        body = {**GENERATE_BODY, "type": "pdf", "profile": "someone-else"}
        response = client.post("/api/generate", json=body, headers={"X-CSRF-Token": "t"})

    assert response.status_code == 200
    assert load_logo.call_args[0][1] == "default"
    assert load_bg.call_args[0][1] == "default"
