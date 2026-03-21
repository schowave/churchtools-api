from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.auth import login, login_page, logout, overview
from app.config import settings


@pytest.fixture
def templates_mock():
    templates_mock = MagicMock(spec=Jinja2Templates)
    with patch("app.api.auth.templates", templates_mock):
        yield templates_mock


@pytest.fixture
def config_mock():
    values = {"CHURCHTOOLS_BASE": "test.church.tools", "CHURCHTOOLS_BASE_URL": "https://test.church.tools"}
    with (
        patch.object(settings, "churchtools_base", values["CHURCHTOOLS_BASE"]),
        patch.object(settings, "churchtools_base_url", values["CHURCHTOOLS_BASE_URL"]),
        patch.object(settings, "version", "0.0.0-test"),
    ):
        yield values


@pytest.mark.asyncio
async def test_login_page(templates_mock, config_mock):
    # Mock request without login token (not logged in)
    request_mock = MagicMock(spec=Request)
    request_mock.cookies.get.return_value = None

    # Call the function
    result = await login_page(request_mock)

    # Check that templates.TemplateResponse was called with correct parameters
    templates_mock.TemplateResponse.assert_called_once()
    call_args = templates_mock.TemplateResponse.call_args[0]
    context = call_args[1]

    assert call_args[0] == "login.html"
    assert "request" in context
    assert "base_url" in context
    assert context["base_url"] == config_mock["CHURCHTOOLS_BASE"]

    # Check that the result is what was returned by templates.TemplateResponse
    assert result == templates_mock.TemplateResponse.return_value


@pytest.mark.asyncio
async def test_login_page_already_logged_in(config_mock):
    # Mock request with login token (already logged in)
    request_mock = MagicMock(spec=Request)
    request_mock.cookies.get.return_value = "test_token"

    result = await login_page(request_mock)

    assert isinstance(result, RedirectResponse)
    assert result.status_code == 303
    assert result.headers["location"] == "/appointments"


@pytest.mark.asyncio
async def test_login_success(config_mock):
    # Mock request
    request_mock = MagicMock(spec=Request)

    # Mock httpx client
    client = AsyncMock()

    # Mock successful login response
    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"data": {"personId": 123}}
    login_response.cookies = {"session": "test_session"}
    client.post.return_value = login_response

    # Mock successful token response
    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {"data": "test_token"}
    client.get.return_value = token_response

    # Call the function
    result = await login(request_mock, username="testuser", password="testpass", client=client)

    # Check that client.post was called with correct parameters
    client.post.assert_called_once_with(
        f"{config_mock['CHURCHTOOLS_BASE_URL']}/api/login",
        json={"password": "testpass", "rememberMe": True, "username": "testuser"},
    )

    # Check that client.get was called with correct parameters
    client.get.assert_called_once_with(
        f"{config_mock['CHURCHTOOLS_BASE_URL']}/api/persons/123/logintoken", cookies=login_response.cookies
    )

    # Check that the result is a RedirectResponse
    assert isinstance(result, RedirectResponse)
    assert result.status_code == 303
    assert result.headers["location"] == "/appointments"

    # Check that the cookie was set
    cookie_header = None
    for header in result.raw_headers:
        if header[0] == b"set-cookie":
            cookie_header = header
            break

    assert cookie_header is not None, "No set-cookie header found"
    assert b"login_token=test_token" in cookie_header[1]


@pytest.mark.asyncio
async def test_login_failure(templates_mock, config_mock):
    # Mock request
    request_mock = MagicMock(spec=Request)

    # Mock httpx client
    client = AsyncMock()

    # Mock failed login response
    login_response = MagicMock()
    login_response.status_code = 401
    client.post.return_value = login_response

    # Call the function
    result = await login(request_mock, username="testuser", password="wrongpass", client=client)

    # Check that templates.TemplateResponse was called with correct parameters
    templates_mock.TemplateResponse.assert_called_once()
    call_args = templates_mock.TemplateResponse.call_args[0]
    context = call_args[1]

    assert call_args[0] == "login.html"
    assert "request" in context
    assert "base_url" in context
    assert "error" in context
    assert context["base_url"] == config_mock["CHURCHTOOLS_BASE"]
    assert context["error"] == "Benutzername oder Passwort ungültig."

    # Check that the result is what was returned by templates.TemplateResponse
    assert result == templates_mock.TemplateResponse.return_value


@pytest.mark.asyncio
async def test_login_token_failure(templates_mock, config_mock):
    # Mock request
    request_mock = MagicMock(spec=Request)

    # Mock httpx client
    client = AsyncMock()

    # Mock successful login response
    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {"data": {"personId": 123}}
    login_response.cookies = {"session": "test_session"}
    client.post.return_value = login_response

    # Mock failed token response
    token_response = MagicMock()
    token_response.status_code = 401
    client.get.return_value = token_response

    # Call the function
    result = await login(request_mock, username="testuser", password="testpass", client=client)

    # Check that templates.TemplateResponse was called with correct parameters
    templates_mock.TemplateResponse.assert_called_once()
    call_args = templates_mock.TemplateResponse.call_args[0]
    context = call_args[1]

    assert call_args[0] == "login.html"
    assert "request" in context
    assert "base_url" in context
    assert "error" in context
    assert context["base_url"] == config_mock["CHURCHTOOLS_BASE"]
    assert context["error"] == "Login-Token konnte nicht abgerufen werden."

    # Check that the result is what was returned by templates.TemplateResponse
    assert result == templates_mock.TemplateResponse.return_value


@pytest.mark.asyncio
async def test_logout():
    # Mock httpx client
    client = AsyncMock()
    client.post.return_value = MagicMock(status_code=200)

    # Mock request with login token
    request_mock = MagicMock(spec=Request)
    request_mock.cookies.get.return_value = "test_token"

    # Call the function
    result = await logout(request_mock, client=client)

    # Check that the ChurchTools API logout was called
    client.post.assert_called_once()

    # Check that the result is a RedirectResponse
    assert isinstance(result, RedirectResponse)
    assert result.status_code == 303
    assert result.headers["location"] == "/"

    # Check that the cookie was deleted
    cookie_header = None
    for header in result.raw_headers:
        if header[0] == b"set-cookie":
            cookie_header = header
            break

    assert cookie_header is not None, "No set-cookie header found"
    assert b"login_token=" in cookie_header[1]
    assert b"Max-Age=0" in cookie_header[1]


@pytest.mark.asyncio
async def test_overview_with_token(templates_mock, config_mock):
    # Mock request with login_token
    request_mock = MagicMock(spec=Request)
    request_mock.cookies.get.return_value = "test_token"

    # Call the function
    result = await overview(request_mock)

    # Check that templates.TemplateResponse was called with correct parameters
    templates_mock.TemplateResponse.assert_called_once()
    call_args = templates_mock.TemplateResponse.call_args[0]
    context = call_args[1]

    assert call_args[0] == "overview.html"
    assert "request" in context
    assert "base_url" in context
    assert context["base_url"] == config_mock["CHURCHTOOLS_BASE"]

    # Check that the result is what was returned by templates.TemplateResponse
    assert result == templates_mock.TemplateResponse.return_value


@pytest.mark.asyncio
async def test_overview_without_token():
    # Mock request without login_token
    request_mock = MagicMock(spec=Request)
    request_mock.cookies.get.return_value = None

    # Call the function
    result = await overview(request_mock)

    # Check that the result is a RedirectResponse
    assert isinstance(result, RedirectResponse)
    assert result.status_code == 303
    assert result.headers["location"] == "/"


if __name__ == "__main__":
    import unittest

    unittest.main()
