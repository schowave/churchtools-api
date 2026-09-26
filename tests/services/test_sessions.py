"""Server-side sessions: the cookie holds a random id, the ChurchTools token stays on the server."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.main import app
from app.models import LoginSession
from app.services import sessions
from app.web import get_http_client

pytestmark = pytest.mark.real_sessions


@pytest.fixture
def session_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sessions.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with patch("app.database.SessionLocal", factory):
        yield factory


# --- store ------------------------------------------------------------------


def test_session_roundtrip_stores_only_the_hash(session_db):
    session_id = sessions.create_session("ct-login-token")

    assert sessions.get_session_token(session_id) == "ct-login-token"
    with session_db() as db:
        stored = db.query(LoginSession).one()
    assert stored.id_hash != session_id
    assert session_id not in stored.id_hash


def test_unknown_session_returns_none(session_db):
    assert sessions.get_session_token("not-a-session") is None


def test_expired_session_is_rejected_and_removed(session_db):
    session_id = sessions.create_session("ct-login-token")
    with session_db() as db:
        row = db.query(LoginSession).one()
        row.expires_at = row.created_at - timedelta(seconds=1)
        db.commit()

    assert sessions.get_session_token(session_id) is None
    with session_db() as db:
        assert db.query(LoginSession).count() == 0


def test_delete_and_purge(session_db):
    keep = sessions.create_session("a")
    gone = sessions.create_session("b")
    expired = sessions.create_session("c")
    sessions.delete_session(gone)
    with session_db() as db:
        row = db.get(LoginSession, sessions._hash(expired))
        row.expires_at = row.created_at - timedelta(seconds=1)
        db.commit()

    sessions.purge_expired_sessions()

    assert sessions.get_session_token(keep) == "a"
    with session_db() as db:
        assert db.query(LoginSession).count() == 1


# --- login / logout flow ------------------------------------------------------


def _response(status_code, payload=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload or {}
    response.cookies = {}
    return response


@pytest.fixture
def churchtools():
    http_client = AsyncMock()
    http_client.post.return_value = _response(200, {"data": {"personId": 7}})
    http_client.get.return_value = _response(200, {"data": "ct-login-token"})
    app.dependency_overrides[get_http_client] = lambda: http_client
    yield http_client
    app.dependency_overrides.clear()


def _client():
    return TestClient(app, cookies={"csrf_token": "t"}, follow_redirects=False)


def _login(client):
    return client.post("/", data={"username": "u", "password": "p"}, headers={"X-CSRF-Token": "t"})


def test_login_sets_opaque_session_cookie(session_db, churchtools):
    client = _client()
    response = _login(client)

    assert response.status_code == 303
    set_cookie = response.headers["set-cookie"]
    session_id = response.cookies[settings.cookie_session]
    assert session_id and session_id != "ct-login-token"
    assert "ct-login-token" not in set_cookie
    assert "HttpOnly" in set_cookie
    assert f"Max-Age={int(sessions.SESSION_LIFETIME.total_seconds())}" in set_cookie
    assert sessions.get_session_token(session_id) == "ct-login-token"

    assert client.get("/overview").status_code == 200


def test_unknown_session_id_redirects_and_clears_cookies(session_db, churchtools):
    client = TestClient(
        app, cookies={settings.cookie_session: "forged", "login_token": "legacy"}, follow_redirects=False
    )
    response = client.get("/overview")

    assert response.status_code == 303
    cleared = response.headers.get_list("set-cookie")
    assert any(c.startswith(f'{settings.cookie_session}=""') for c in cleared)
    assert any(c.startswith('login_token=""') for c in cleared)


def test_logout_ends_server_session(session_db, churchtools):
    client = _client()
    session_id = _login(client).cookies[settings.cookie_session]

    with patch("app.api.auth.forget_login_token") as forget:
        response = client.post("/logout", headers={"X-CSRF-Token": "t"})

    assert response.status_code == 303
    assert sessions.get_session_token(session_id) is None
    forget.assert_called_once_with("ct-login-token")
    cleared = next(c for c in response.headers.get_list("set-cookie") if c.startswith(f"{settings.cookie_session}="))
    assert "HttpOnly" in cleared and "SameSite" in cleared
    assert client.get("/overview").status_code == 303
