import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import httpx
from app.api.auth import login, login_page, logout, overview
from app.config import Config

class TestAuth(unittest.TestCase):
    def setUp(self):
        # Mock templates
        self.templates_mock = MagicMock(spec=Jinja2Templates)
        self.templates_patch = patch('app.api.auth.templates', self.templates_mock)
        self.templates_patch.start()
        
        # Mock Config
        self.config_mock = {
            'CHURCHTOOLS_BASE': 'test.church.tools',
            'CHURCHTOOLS_BASE_URL': 'https://test.church.tools'
        }
        self.config_patch = patch.multiple('app.api.auth.Config', 
                                          CHURCHTOOLS_BASE=self.config_mock['CHURCHTOOLS_BASE'],
                                          CHURCHTOOLS_BASE_URL=self.config_mock['CHURCHTOOLS_BASE_URL'])
        self.config_patch.start()
    
    def tearDown(self):
        self.templates_patch.stop()
        self.config_patch.stop()
    
    @pytest.mark.asyncio
    async def test_login_page(self):
        # Mock request
        request_mock = MagicMock(spec=Request)
        
        # Call the function
        result = await login_page(request_mock)
        
        # Check that templates.TemplateResponse was called with correct parameters
        self.templates_mock.TemplateResponse.assert_called_once_with(
            "login.html", 
            {"request": request_mock, "base_url": self.config_mock['CHURCHTOOLS_BASE']}
        )
        
        # Check that the result is what was returned by templates.TemplateResponse
        self.assertEqual(result, self.templates_mock.TemplateResponse.return_value)
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_login_success(self, mock_client):
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
            f'{self.config_mock["CHURCHTOOLS_BASE_URL"]}/api/login',
            json={"password": "testpass", "rememberMe": True, "username": "testuser"}
        )
        
        # Check that client.get was called with correct parameters
        client_instance.get.assert_called_once_with(
            f'{self.config_mock["CHURCHTOOLS_BASE_URL"]}/api/persons/123/logintoken',
            cookies=login_response.cookies
        )
        
        # Check that the result is a RedirectResponse
        self.assertIsInstance(result, RedirectResponse)
        self.assertEqual(result.status_code, 303)
        self.assertEqual(result.headers['location'], '/overview')
        
        # Check that the cookie was set
        self.assertEqual(result.raw_headers[0][0], b'set-cookie')
        self.assertIn(b'login_token=test_token', result.raw_headers[0][1])
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_login_failure(self, mock_client):
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
        self.templates_mock.TemplateResponse.assert_called_once_with(
            "login.html",
            {"request": request_mock, "base_url": self.config_mock['CHURCHTOOLS_BASE'], 
             "error": "Invalid username or password."}
        )
        
        # Check that the result is what was returned by templates.TemplateResponse
        self.assertEqual(result, self.templates_mock.TemplateResponse.return_value)
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_login_token_failure(self, mock_client):
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
        self.templates_mock.TemplateResponse.assert_called_once_with(
            "login.html",
            {"request": request_mock, "base_url": self.config_mock['CHURCHTOOLS_BASE'], 
             "error": "Failed to retrieve login token."}
        )
        
        # Check that the result is what was returned by templates.TemplateResponse
        self.assertEqual(result, self.templates_mock.TemplateResponse.return_value)
    
    @pytest.mark.asyncio
    async def test_logout(self):
        # Call the function
        result = await logout()
        
        # Check that the result is a RedirectResponse
        self.assertIsInstance(result, RedirectResponse)
        self.assertEqual(result.status_code, 303)
        self.assertEqual(result.headers['location'], '/overview')
        
        # Check that the cookie was deleted
        self.assertEqual(result.raw_headers[0][0], b'set-cookie')
        self.assertIn(b'login_token=', result.raw_headers[0][1])
        self.assertIn(b'Max-Age=0', result.raw_headers[0][1])
    
    @pytest.mark.asyncio
    async def test_overview_with_token(self):
        # Mock request with login_token
        request_mock = MagicMock(spec=Request)
        request_mock.cookies.get.return_value = "test_token"
        
        # Call the function
        result = await overview(request_mock)
        
        # Check that templates.TemplateResponse was called with correct parameters
        self.templates_mock.TemplateResponse.assert_called_once_with(
            "overview.html",
            {"request": request_mock, "base_url": self.config_mock['CHURCHTOOLS_BASE']}
        )
        
        # Check that the result is what was returned by templates.TemplateResponse
        self.assertEqual(result, self.templates_mock.TemplateResponse.return_value)
    
    @pytest.mark.asyncio
    async def test_overview_without_token(self):
        # Mock request without login_token
        request_mock = MagicMock(spec=Request)
        request_mock.cookies.get.return_value = None
        
        # Call the function
        result = await overview(request_mock)
        
        # Check that the result is a RedirectResponse
        self.assertIsInstance(result, RedirectResponse)
        self.assertEqual(result.status_code, 303)
        self.assertEqual(result.headers['location'], '/')

if __name__ == '__main__':
    unittest.main()