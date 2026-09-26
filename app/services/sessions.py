"""Server-side login sessions: the browser gets a random id, the ChurchTools token stays here."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from app import database
from app.models import LoginSession

SESSION_LIFETIME = timedelta(days=30)


def _hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def _now() -> datetime:
    # Stored naive in UTC (SQLite has no timezone support)
    return datetime.now(UTC).replace(tzinfo=None)


def create_session(login_token: str) -> str:
    """Store the token and return a new random session id for the cookie."""
    session_id = secrets.token_urlsafe(32)
    now = _now()
    with database.SessionLocal() as db:
        db.add(
            LoginSession(
                id_hash=_hash(session_id),
                login_token=login_token,
                created_at=now,
                expires_at=now + SESSION_LIFETIME,
            )
        )
        db.commit()
    return session_id


def get_session_token(session_id: str) -> str | None:
    """Return the ChurchTools token for a live session, or None (unknown or expired)."""
    with database.SessionLocal() as db:
        row = db.get(LoginSession, _hash(session_id))
        if row is None:
            return None
        if row.expires_at <= _now():
            db.delete(row)
            db.commit()
            return None
        return row.login_token


def delete_session(session_id: str) -> None:
    with database.SessionLocal() as db:
        db.query(LoginSession).filter(LoginSession.id_hash == _hash(session_id)).delete()
        db.commit()


def purge_expired_sessions() -> None:
    with database.SessionLocal() as db:
        db.query(LoginSession).filter(LoginSession.expires_at <= _now()).delete()
        db.commit()
