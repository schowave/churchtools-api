"""Error responses must not leak request input or framework internals."""

from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.web import get_http_client

client = TestClient(app, cookies={"csrf_token": "t"})


@pytest.fixture(autouse=True)
def _http_client_override():
    app.dependency_overrides[get_http_client] = lambda: AsyncMock()
    yield
    app.dependency_overrides.clear()


def test_validation_error_hides_input_and_internals():
    secret = "SECRET-INPUT-VALUE"
    response = client.post(
        "/api/generate",
        json={"type": "exe", "start_date": secret},
        headers={"X-CSRF-Token": "t"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert secret not in response.text
    assert "pydantic" not in response.text
    assert {"loc", "msg"} <= set(body["detail"][0])


def test_churchtools_http_error_becomes_502():
    upstream = AsyncMock()
    upstream.get.side_effect = httpx2.ConnectError("connection refused")
    app.dependency_overrides[get_http_client] = lambda: upstream

    response = TestClient(app, cookies={"session": "tok"}).get(
        "/api/events", params={"start_date": "2026-01-01", "end_date": "2026-01-07", "calendar_ids": "1"}
    )

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_error"
    assert "connection refused" not in response.text


def test_unhandled_exception_becomes_json_500():
    with patch("app.api.events.fetch_events", AsyncMock(side_effect=RuntimeError("secret internals"))):
        response = TestClient(app, raise_server_exceptions=False, cookies={"session": "tok"}).get(
            "/api/events", params={"start_date": "2026-01-01", "end_date": "2026-01-07", "calendar_ids": "1"}
        )

    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    assert "secret internals" not in response.text
