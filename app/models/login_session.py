from sqlalchemy import Column, DateTime, String, Text

from app.database import Base


class LoginSession(Base):
    """Server-side login session. The browser only holds the random session id."""

    __tablename__ = "login_sessions"

    id_hash = Column(String(64), primary_key=True)  # sha256 of the session id, never the id itself
    login_token = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
