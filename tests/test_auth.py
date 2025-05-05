import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import httpx
from app.api.auth import login, login_page, logout, overview
from app.config import Config

@pytest.fixture
def templates_mock():
    templates_mock = MagicMock(spec=Jinja2Templates)
    with patch('app.api.auth.templates', templates_mock):
        yield templates_mock

@pytest.fixture
def config_mock():
    config_mock = {
        'CHURCHTOOLS_BASE': 'test.church.tools',
        'CHURCHTOOLS_BASE_URL': 'https://test.church.tools'
    }
    with patch.multiple('app.api.auth.Config',
                      CHURCHTOOLS_BASE=config_mock['CHURCHTOOLS_BASE'],
                      CHURCHTOOLS_BASE_URL=config_mock['CHURCHTOOLS_BASE_URL']):
        yield config_mock

@pytest.mark.asyncio
async def test_login_page(templates_mock, config_mock):
    # Mock request
    request_mock = MagicMock(spec=Request)
    
    # Call the function
    result = await login_page(request_mock)
    
    # Check that templates.TemplateResponse was called with correct parameters
    templates_mock.TemplateResponse.assert_called_once()
    call_args = templates_mock.TemplateResponse.call_args[0]
    context = call_args[1]
    
    assert call_args[0] == "login.html"
    assert 'request' in context
    assert 'base_url' in context
    assert context['base_url'] == config_mock['CHURCHTOOLS_BASE']
    
    # Check that the result is what was returned by templates.TemplateResponse
    assert result == templates_mock.TemplateResponse.return_value

@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_login_success(mock_client, config_mock):
    # Mock request
    request_mock = MagicMock(spec=Request)
    
    # Mock httpx client and responses
    client_instance = AsyncMock()
    mock_client.return_value.__aenter__.return_value = client_instance
    
    # Mock successful login response
    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {'data': {'personId': 123}}
    login_response.cookies = {'session': 'test_session'}
    client_instance.post.return_value = login_response
    
    # Mock successful token response
    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {'data': 'test_token'}
    client_instance.get.return_value = token_response
    
    # Call the function
    result = await login(request_mock, username="testuser", password="testpass")
    
    # Check that client.post was called with correct parameters
    client_instance.post.assert_called_once_with(
        f'{config_mock["CHURCHTOOLS_BASE_URL"]}/api/login',
        json={"password": "testpass", "rememberMe": True, "username": "testuser"}
    )
    
    # Check that client.get was called with correct parameters
    client_instance.get.assert_called_once_with(
        f'{config_mock["CHURCHTOOLS_BASE_URL"]}/api/persons/123/logintoken',
        cookies=login_response.cookies
    )
    
    # Check that the result is a RedirectResponse
    assert isinstance(result, RedirectResponse)
    assert result.status_code == 303
    assert result.headers['location'] == '/overview'
    
    # Check that the cookie was set
    cookie_header = None
    for header in result.raw_headers:
        if header[0] == b'set-cookie':
            cookie_header = header
            break
    
    assert cookie_header is not None, "No set-cookie header found"
    assert b'login_token=test_token' in cookie_header[1]

@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_login_failure(mock_client, templates_mock, config_mock):
    # Mock request
    request_mock = MagicMock(spec=Request)
    
    # Mock httpx client and responses
    client_instance = AsyncMock()
    mock_client.return_value.__aenter__.return_value = client_instance
    
    # Mock failed login response
    login_response = MagicMock()
    login_response.status_code = 401
    client_instance.post.return_value = login_response
    
    # Call the function
    result = await login(request_mock, username="testuser", password="wrongpass")
    
    # Check that templates.TemplateResponse was called with correct parameters
    templates_mock.TemplateResponse.assert_called_once()
    call_args = templates_mock.TemplateResponse.call_args[0]
    context = call_args[1]
    
    assert call_args[0] == "login.html"
    assert 'request' in context
    assert 'base_url' in context
    assert 'error' in context
    assert context['base_url'] == config_mock['CHURCHTOOLS_BASE']
    assert context['error'] == "Invalid username or password."
    
    # Check that the result is what was returned by templates.TemplateResponse
    assert result == templates_mock.TemplateResponse.return_value

@pytest.mark.asyncio
@patch('httpx.AsyncClient')
async def test_login_token_failure(mock_client, templates_mock, config_mock):
    # Mock request
    request_mock = MagicMock(spec=Request)
    
    # Mock httpx client and responses
    client_instance = AsyncMock()
    mock_client.return_value.__aenter__.return_value = client_instance
    
    # Mock successful login response
    login_response = MagicMock()
    login_response.status_code = 200
    login_response.json.return_value = {'data': {'personId': 123}}
    login_response.cookies = {'session': 'test_session'}
    client_instance.post.return_value = login_response
    
    # Mock failed token response
    token_response = MagicMock()
    token_response.status_code = 401
    client_instance.get.return_value = token_response
    
    # Call the function
    result = await login(request_mock, username="testuser", password="testpass")
    
    # Check that templates.TemplateResponse was called with correct parameters
    templates_mock.TemplateResponse.assert_called_once()
    call_args = templates_mock.TemplateResponse.call_args[0]
    context = call_args[1]
    
    assert call_args[0] == "login.html"
    assert 'request' in context
    assert 'base_url' in context
    assert 'error' in context
    assert context['base_url'] == config_mock['CHURCHTOOLS_BASE']
    assert context['error'] == "Failed to retrieve login token."
    
    # Check that the result is what was returned by templates.TemplateResponse
    assert result == templates_mock.TemplateResponse.return_value

@pytest.mark.asyncio
async def test_logout():
    # Call the function
    result = await logout()
    
    # Check that the result is a RedirectResponse
    assert isinstance(result, RedirectResponse)
    assert result.status_code == 303
    assert result.headers['location'] == '/overview'
    
    # Check that the cookie was deleted
    cookie_header = None
    for header in result.raw_headers:
        if header[0] == b'set-cookie':
            cookie_header = header
            break
    
    assert cookie_header is not None, "No set-cookie header found"
    assert b'login_token=' in cookie_header[1]
    assert b'Max-Age=0' in cookie_header[1]

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
    assert 'request' in context
    assert 'base_url' in context
    assert context['base_url'] == config_mock['CHURCHTOOLS_BASE']
    
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
    assert result.headers['location'] == '/'

if __name__ == '__main__':
    unittest.main()