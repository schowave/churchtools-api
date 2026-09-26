from unittest.mock import AsyncMock, MagicMock, patch

import httpx2
import pytest
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.auth import login, login_page, logout, overview
from app.schemas import CurrentUser


@pytest.fixture
def templates_mock():
    templates_mock = MagicMock(spec=Jinja2Templates)
    with patch("app.api.auth.templates", templates_mock):
        yield templates_mock


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
    context = call_args[2]

    assert call_args[1] == "login.html"
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
async def test_login_page_shows_hint_after_expired_form(templates_mock, config_mock):
    request_mock = MagicMock(spec=Request)
    request_mock.cookies.get.return_value = None
    request_mock.query_params = {"hinweis": "abgelaufen"}

    await login_page(request_mock)

    context = templates_mock.TemplateResponse.call_args[0][2]
    assert context["error"] == "Die Seite war zu lange geöffnet. Bitte erneut anmelden."


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

    # Check that client.get was called with correct parameters (the name lookup for the navigation follows)
    client.get.assert_any_call(
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
    # Autouse fixture maps the session id to the token; the real store is covered in test_sessions.py
    assert b"session=test_token" in cookie_header[1]
    assert b"HttpOnly" in cookie_header[1]


@pytest.mark.asyncio
async def test_login_stores_display_name_for_navigation(config_mock):
    client = AsyncMock()
    login_response = MagicMock(status_code=200, cookies={})
    login_response.json.return_value = {"data": {"personId": 7}}
    client.post.return_value = login_response
    token_response = MagicMock(status_code=200)
    token_response.json.return_value = {"data": "token"}
    client.get.return_value = token_response
    user = CurrentUser(id=7, first_name="Erika", last_name="Muster")

    with (
        patch("app.api.auth.fetch_current_user", AsyncMock(return_value=user)),
        patch("app.api.auth.sessions.create_session", return_value="sid") as create_session,
    ):
        await login(MagicMock(spec=Request), username="u", password="p", client=client)

    create_session.assert_called_once_with("token", "Erika Muster")


@pytest.mark.asyncio
async def test_login_succeeds_without_display_name(config_mock):
    client = AsyncMock()
    login_response = MagicMock(status_code=200, cookies={})
    login_response.json.return_value = {"data": {"personId": 7}}
    client.post.return_value = login_response
    token_response = MagicMock(status_code=200)
    token_response.json.return_value = {"data": "token"}
    client.get.return_value = token_response

    with (
        patch("app.api.auth.fetch_current_user", AsyncMock(side_effect=httpx2.ConnectError("down"))),
        patch("app.api.auth.sessions.create_session", return_value="sid") as create_session,
    ):
        result = await login(MagicMock(spec=Request), username="u", password="p", client=client)

    assert result.status_code == 303
    create_session.assert_called_once_with("token", None)


@pytest.mark.asyncio
async def test_login_refused_for_person_without_app_access(templates_mock, config_mock):
    client = AsyncMock()
    login_response = MagicMock(status_code=200, cookies={})
    login_response.json.return_value = {"data": {"personId": 7}}
    client.post.return_value = login_response
    token_response = MagicMock(status_code=200)
    token_response.json.return_value = {"data": "token"}
    client.get.return_value = token_response

    with (
        patch("app.services.auth.validate_login_token", AsyncMock(return_value=False)),
        patch("app.api.auth.sessions.create_session") as create_session,
    ):
        await login(MagicMock(spec=Request), username="u", password="p", client=client)

    create_session.assert_not_called()
    context = templates_mock.TemplateResponse.call_args[0][2]
    assert "keinen Zugriff" in context["error"]
    assert templates_mock.TemplateResponse.call_args[1]["status_code"] == 403


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
    context = call_args[2]

    assert call_args[1] == "login.html"
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
    context = call_args[2]

    assert call_args[1] == "login.html"
    assert "base_url" in context
    assert "error" in context
    assert context["base_url"] == config_mock["CHURCHTOOLS_BASE"]
    assert context["error"] == "Login-Token konnte nicht abgerufen werden."

    # Check that the result is what was returned by templates.TemplateResponse
    assert result == templates_mock.TemplateResponse.return_value


@pytest.mark.asyncio
async def test_login_churchtools_unreachable(templates_mock, config_mock):
    client = AsyncMock()
    client.post.side_effect = httpx2.ConnectError("connection refused")

    await login(MagicMock(spec=Request), username="testuser", password="testpass", client=client)

    _, kwargs = templates_mock.TemplateResponse.call_args
    context = templates_mock.TemplateResponse.call_args[0][2]
    assert context["error"] == "ChurchTools ist gerade nicht erreichbar. Bitte später erneut versuchen."
    assert kwargs["status_code"] == 502


@pytest.mark.asyncio
async def test_login_unexpected_response(templates_mock, config_mock):
    """A 200 without the expected JSON (e.g. an HTML page) shows a message instead of crashing."""
    client = AsyncMock()
    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.side_effect = ValueError("not json")
    client.post.return_value = login_response

    await login(MagicMock(spec=Request), username="testuser", password="testpass", client=client)

    context = templates_mock.TemplateResponse.call_args[0][2]
    assert context["error"] == "Unerwartete Antwort von ChurchTools. Anmeldung nicht möglich."


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
    assert b'session=""' in cookie_header[1]
    assert b"Max-Age=0" in cookie_header[1]


@pytest.mark.asyncio
async def test_overview_redirects_to_start_page():
    """The former start page stays reachable for bookmarks."""
    result = await overview()

    assert result.status_code == 301
    assert result.headers["location"] == "/appointments"


if __name__ == "__main__":
    import unittest

    unittest.main()
