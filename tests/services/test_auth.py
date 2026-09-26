from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import auth


def _whoami_response(status_code=200, person_id=42):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {"data": {"id": person_id}}
    return response


@pytest.fixture(autouse=True)
def _clear_token_cache():
    auth._valid_token_cache.clear()
    yield
    auth._valid_token_cache.clear()


@pytest.mark.real_token_validation
async def test_token_valid_for_real_person():
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=42)
    assert await auth.validate_login_token("good", client) is True


@pytest.mark.real_token_validation
async def test_token_invalid_when_churchtools_returns_anonymous_user():
    # ChurchTools answers invalid tokens with HTTP 200 and the anonymous user (id -1).
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=-1)
    assert await auth.validate_login_token("bogus", client) is False


@pytest.mark.real_token_validation
async def test_token_invalid_on_401():
    client = AsyncMock()
    client.get.return_value = _whoami_response(status_code=401)
    assert await auth.validate_login_token("expired", client) is False


@pytest.mark.real_token_validation
async def test_valid_token_is_cached():
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=42)
    await auth.validate_login_token("good", client)
    await auth.validate_login_token("good", client)
    assert client.get.call_count == 1


@pytest.mark.real_token_validation
async def test_invalid_token_is_not_cached():
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=-1)
    await auth.validate_login_token("bogus", client)
    await auth.validate_login_token("bogus", client)
    assert client.get.call_count == 2
