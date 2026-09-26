"""Server-side login sessions: the browser gets a random id, the ChurchTools token stays here.

The DB holds sha256(id) for lookup and the token encrypted with a key derived from the id, so the
database file alone reveals no usable token.
"""

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app import database
from app.models import LoginSession

SESSION_LIFETIME = timedelta(days=30)
# Every Fernet token starts with the version byte 0x80, base64-encoded as "gAAAAA"
FERNET_PREFIX = "gAAAAA"


def _hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def _fernet(session_id: str) -> Fernet:
    # The id has 256 random bits, so HKDF without salt is enough; "info" keeps it apart from the lookup hash
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"churchtools-login-token").derive(
        session_id.encode()
    )
    return Fernet(base64.urlsafe_b64encode(key))


def _encrypt(session_id: str, login_token: str) -> str:
    return _fernet(session_id).encrypt(login_token.encode()).decode()


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
                login_token=_encrypt(session_id, login_token),
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
        if not row.login_token.startswith(FERNET_PREFIX):
            # Sessions from before encryption (v7.1) hold the plain token: encrypt it, keep the user logged in
            login_token = row.login_token
            row.login_token = _encrypt(session_id, login_token)
            db.commit()
            return login_token
        try:
            return _fernet(session_id).decrypt(row.login_token.encode()).decode()
        except InvalidToken:
            return None


def get_session_expiry(session_id: str) -> datetime | None:
    """Expiry (naive UTC) of a session, or None if it does not exist."""
    with database.SessionLocal() as db:
        row = db.get(LoginSession, _hash(session_id))
        return row.expires_at if row else None


def delete_session(session_id: str) -> None:
    with database.SessionLocal() as db:
        db.query(LoginSession).filter(LoginSession.id_hash == _hash(session_id)).delete()
        db.commit()


def purge_expired_sessions() -> None:
    with database.SessionLocal() as db:
        db.query(LoginSession).filter(LoginSession.expires_at <= _now()).delete()
        db.commit()
