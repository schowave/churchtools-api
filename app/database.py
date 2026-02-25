from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import Config

DEFAULT_SETTING_NAME = "default"

# SQLite database URL
SQLALCHEMY_DATABASE_URL = f"sqlite:///{Config.DB_PATH}"

# Create engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_schema():
    # Import models so they register with Base.metadata before creating tables
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
