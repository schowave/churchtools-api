"""Error responses must not leak request input or framework internals."""

from unittest.mock import AsyncMock

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
