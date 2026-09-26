from unittest.mock import AsyncMock, MagicMock, patch

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


# --- access restriction (ALLOWED_PERSON_IDS / ALLOWED_GROUP_IDS) ------------------------


def _groups_response(status_code=200, groups=()):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {
        "data": [
            {"group": {"domainType": "group", "domainIdentifier": str(group_id)}, "groupMemberStatus": status}
            for group_id, status in groups
        ]
    }
    return response


def _restrict(persons="", groups=""):
    return patch.multiple(auth.settings, allowed_person_ids=persons, allowed_group_ids=groups)


@pytest.mark.real_token_validation
async def test_everyone_with_a_churchtools_login_has_access_without_restriction():
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=42)
    with _restrict():
        assert await auth.validate_login_token("good", client) is True
    assert client.get.call_count == 1  # no group lookup


@pytest.mark.real_token_validation
@pytest.mark.parametrize(("allowed", "expected"), [("7, 42", True), ("7", False)])
async def test_person_allowlist(allowed, expected):
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=42)
    with _restrict(persons=allowed):
        assert await auth.validate_login_token("good", client) is expected


@pytest.mark.real_token_validation
@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        ([(5, "active"), (12, "active")], True),
        ([(5, "active")], False),
        ([(12, "requested")], False),  # a pending membership request is not membership
    ],
)
async def test_group_allowlist(groups, expected):
    client = AsyncMock()
    client.get.side_effect = [_whoami_response(person_id=42), _groups_response(groups=groups)]
    with _restrict(groups="12"):
        assert await auth.validate_login_token("good", client) is expected
    client.get.assert_called_with(
        f"{auth.settings.churchtools_base_url}/api/persons/42/groups", headers={"Authorization": "Login good"}
    )


@pytest.mark.real_token_validation
async def test_group_lookup_failure_denies_access():
    client = AsyncMock()
    client.get.side_effect = [_whoami_response(person_id=42), _groups_response(status_code=403)]
    with _restrict(groups="12"):
        assert await auth.validate_login_token("good", client) is False


@pytest.mark.real_token_validation
async def test_person_allowlist_skips_group_lookup():
    client = AsyncMock()
    client.get.return_value = _whoami_response(person_id=42)
    with _restrict(persons="42", groups="12"):
        assert await auth.validate_login_token("good", client) is True
    assert client.get.call_count == 1
