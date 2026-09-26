"""Failed logins are rate limited per username and per client IP."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import auth as auth_api
from app.main import app
from app.services.rate_limit import LoginRateLimiter
from app.web import get_http_client


def _response(status_code, payload=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload or {}
    response.cookies = {}
    return response


@pytest.fixture
def churchtools():
    http_client = AsyncMock()
    http_client.post.return_value = _response(401)
    app.dependency_overrides[get_http_client] = lambda: http_client
    auth_api.login_rate_limiter.reset()
    auth_api.ip_rate_limiter.reset()
    yield http_client
    auth_api.login_rate_limiter.reset()
    auth_api.ip_rate_limiter.reset()
    app.dependency_overrides.clear()


def _login(client, password="wrong", username="u"):
    return client.post(
        "/",
        data={"username": username, "password": password, "_csrf_token": "t"},
        headers={"X-CSRF-Token": "t"},
    )


def test_login_blocked_after_too_many_failures(churchtools):
    client = TestClient(app, cookies={"csrf_token": "t"}, follow_redirects=False)
    for _ in range(LoginRateLimiter.DEFAULT_MAX_FAILURES):
        assert _login(client).status_code == 200

    blocked = _login(client)
    assert blocked.status_code == 429
    assert "Zu viele Fehlversuche" in blocked.text
    # Blocked attempts must not reach ChurchTools at all.
    assert churchtools.post.call_count == LoginRateLimiter.DEFAULT_MAX_FAILURES


def test_successful_login_resets_failures(churchtools):
    client = TestClient(app, cookies={"csrf_token": "t"}, follow_redirects=False)
    for _ in range(LoginRateLimiter.DEFAULT_MAX_FAILURES - 1):
        _login(client)

    churchtools.post.return_value = _response(200, {"data": {"personId": 1}})
    churchtools.get.return_value = _response(200, {"data": "login-token"})
    assert _login(client, "right").status_code == 303

    churchtools.post.return_value = _response(401)
    assert _login(client).status_code == 200


def test_username_limit_ignores_case_and_whitespace(churchtools):
    client = TestClient(app, cookies={"csrf_token": "t"}, follow_redirects=False)
    for _ in range(LoginRateLimiter.DEFAULT_MAX_FAILURES):
        _login(client, username="Anna")

    assert _login(client, username=" anna ").status_code == 429
    assert _login(client, username="bob").status_code == 200


def test_login_blocked_per_ip_across_usernames(churchtools):
    client = TestClient(app, cookies={"csrf_token": "t"}, follow_redirects=False)
    for n in range(auth_api.ip_rate_limiter.max_failures):
        assert _login(client, username=f"user{n}").status_code == 200

    assert _login(client, username="someone-else").status_code == 429


def test_own_successful_login_does_not_reset_ip_limit(churchtools):
    # An attacker with an account must not be able to clear the IP's failures between guesses
    client = TestClient(app, cookies={"csrf_token": "t"}, follow_redirects=False)
    churchtools.get.return_value = _response(200, {"data": "login-token"})
    for n in range(auth_api.ip_rate_limiter.max_failures - 1):
        churchtools.post.return_value = _response(401)
        _login(client, username=f"victim{n}")
        churchtools.post.return_value = _response(200, {"data": {"personId": 1}})
        assert _login(client, "right", username="attacker").status_code == 303

    churchtools.post.return_value = _response(401)
    assert _login(client, username="victim-last").status_code == 200
    assert _login(client, username="victim-next").status_code == 429


def test_limiter_window_expires():
    now = [1000.0]
    limiter = LoginRateLimiter(max_failures=2, window_seconds=60, clock=lambda: now[0])
    limiter.record_failure("1.2.3.4")
    limiter.record_failure("1.2.3.4")
    assert limiter.retry_after("1.2.3.4") > 0
    assert limiter.retry_after("5.6.7.8") == 0

    now[0] += 61
    assert limiter.retry_after("1.2.3.4") == 0
