# Best Practices Improvements Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve maintainability, robustness, and developer experience of the ChurchTools API application through 13 targeted improvements.

**Architecture:** Layered FastAPI app with SQLAlchemy ORM, Jinja2 templates, and service layer for ChurchTools API integration and PDF generation. Changes are independent and incremental — each task produces a working, testable state.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, SQLite, Pydantic, ReportLab, httpx, Alembic (new), pydantic-settings (new), structlog (new), HTMX (new), Alpine.js (new)

**Spec:** `docs/superpowers/specs/2026-03-15-best-practices-improvements-design.md`

---

## Chunk 1: Configuration Foundation

### Task 1: Pydantic Settings for Configuration

**Files:**
- Modify: `app/config.py` (rewrite)
- Modify: `app/database.py:4,9` (import change)
- Modify: `app/main.py:3,9,13,15` (remove load_dotenv, Config.validate)
- Modify: `app/api/auth.py:6` (import change)
- Modify: `app/api/appointments.py:10` (import change)
- Modify: `app/services/churchtools_client.py:7` (import change)
- Modify: `app/services/pdf_generator.py:15` (import change)
- Modify: `app/services/jpeg_generator.py:8` (import change)
- Modify: `app/schemas.py` (no change needed — doesn't import Config)
- Modify: `pyproject.toml:6` (add pydantic-settings dep)
- Modify: `requirements.txt` (regenerate)
- Test: `tests/test_config.py` (new)

- [ ] **Step 1: Write failing test for Settings class**

Create `tests/test_config.py`:
```python
import unittest
from unittest.mock import patch


class TestSettings(unittest.TestCase):
    @patch.dict("os.environ", {"CHURCHTOOLS_BASE": "my-church.church.tools"}, clear=False)
    def test_settings_loads_from_env(self):
        # Re-import to pick up patched env
        from app.config import Settings

        s = Settings()
        assert s.churchtools_base == "my-church.church.tools"
        assert s.churchtools_base_url == "https://my-church.church.tools"
        assert s.db_path == "churchtools.db"
        assert s.cookie_login_token == "login_token"

    @patch.dict("os.environ", {"CHURCHTOOLS_BASE": "my-church.church.tools", "CHURCHTOOLS_BASE_URL": "http://custom.url"}, clear=False)
    def test_base_url_overridable(self):
        from app.config import Settings

        s = Settings()
        assert s.churchtools_base_url == "http://custom.url"

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_churchtools_base_raises(self):
        from app.config import Settings

        with self.assertRaises(Exception):
            Settings()

    @patch.dict("os.environ", {"CHURCHTOOLS_BASE": "my-church.church.tools"}, clear=False)
    def test_version_reads_from_pyproject(self):
        from app.config import Settings

        s = Settings()
        assert s.version != "0.0.0"
        assert "." in s.version
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL — `Settings` class doesn't exist yet

- [ ] **Step 3: Add pydantic-settings dependency**

In `pyproject.toml`, add to dependencies list:
```
    "pydantic-settings>=2.7",
```

Run: `venv/bin/pip install -e ".[dev]"`

- [ ] **Step 4: Implement Settings class**

Rewrite `app/config.py`:
```python
import tomllib
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_version() -> str:
    try:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "0.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    churchtools_base: str
    db_path: str = "churchtools.db"
    churchtools_base_url: str = ""
    cookie_login_token: str = "login_token"
    version: str = _read_version()

    @model_validator(mode="after")
    def _set_base_url(self) -> "Settings":
        if not self.churchtools_base_url:
            self.churchtools_base_url = f"https://{self.churchtools_base}"
        return self


settings = Settings()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Update database.py to use new settings**

Change `app/database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

DEFAULT_SETTING_NAME = "default"

SQLALCHEMY_DATABASE_URL = f"sqlite:///{settings.db_path}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_schema():
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 7: Update main.py — remove load_dotenv and Config references**

Change `app/main.py`:
```python
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import appointments, auth
from app.config import settings
from app.database import create_schema


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app = FastAPI(title="ChurchTools API")
app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)

app.include_router(auth.router, tags=["auth"])
app.include_router(appointments.router, tags=["appointments"])

create_schema()
```

Note: Remove the `FILE_DIRECTORY` mkdir since we'll remove file-based generation later. The `E402` per-file-ignore in pyproject.toml can also be removed since `load_dotenv()` is gone.

- [ ] **Step 8: Update all modules importing Config**

`app/api/auth.py` — replace all `Config.` references:
- `from app.config import Config` → `from app.config import settings`
- `Config.COOKIE_LOGIN_TOKEN` → `settings.cookie_login_token`
- `Config.CHURCHTOOLS_BASE_URL` → `settings.churchtools_base_url`
- `Config.CHURCHTOOLS_BASE` → `settings.churchtools_base`
- `Config.VERSION` → `settings.version`

`app/api/appointments.py` — same pattern:
- `from app.config import Config` → `from app.config import settings`
- Replace all `Config.` → `settings.` (lowercase attribute names)
- `Config.FILE_DIRECTORY` → Keep for now (removed in Task 5: in-memory generation)

`app/services/churchtools_client.py`:
- `from app.config import Config` → `from app.config import settings`
- `Config.CHURCHTOOLS_BASE_URL` → `settings.churchtools_base_url`

`app/services/pdf_generator.py`:
- `from app.config import Config` → `from app.config import settings`
- `Config.FILE_DIRECTORY` → `settings.file_directory` (add `file_directory` field to Settings temporarily — removed in Task 5)

`app/services/jpeg_generator.py`:
- `from app.config import Config` → `from app.config import settings`
- `Config.FILE_DIRECTORY` → `settings.file_directory`

Add to `Settings` class temporarily (until in-memory generation removes it):
```python
    file_directory: str = str(Path(__file__).parent.parent / "saved_files")
```

- [ ] **Step 9: Update pyproject.toml ruff config**

Remove the E402 per-file-ignore since `load_dotenv()` is gone:
```toml
# Remove this section entirely:
# [tool.ruff.lint.per-file-ignores]
# "app/main.py" = ["E402"]
```

- [ ] **Step 10: Remove python-dotenv dependency**

In `pyproject.toml`, remove:
```
    "python-dotenv>=1.2.2",
```

pydantic-settings handles .env loading natively.

- [ ] **Step 11: Regenerate requirements.txt**

Run: `venv/bin/pip install -e ".[dev]" && venv/bin/pip freeze --exclude-editable > requirements.txt`

- [ ] **Step 12: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All tests pass. Some existing tests mock `Config` — they'll need updating.

- [ ] **Step 13: Fix broken tests**

Update tests that reference `Config`:
- `tests/test_database.py`: `from app.database import create_schema` still works. The `create_schema` test patches `app.database.engine` which still exists.
- `tests/test_appointments.py` and `tests/test_auth.py`: Patch `app.config.settings` instead of `app.config.Config`.
- `tests/test_pdf_generator.py`: Patch `app.config.settings.file_directory` instead of `Config.FILE_DIRECTORY`.
- `tests/test_utils.py`: No changes needed (doesn't reference Config).

Pattern: Replace `@patch.object(Config, "ATTR", value)` with `@patch("app.config.settings.attr", value)` or use `@patch.dict("os.environ", {...})` and re-instantiate.

- [ ] **Step 14: Run full test suite again**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 15: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`
Expected: Clean

- [ ] **Step 16: Commit**

```bash
git add app/config.py app/database.py app/main.py app/api/ app/services/ app/shared.py pyproject.toml requirements.txt tests/
git commit -m "refactor: replace Config class with pydantic-settings"
```

---

### Task 2: Configurable Timezone

**Files:**
- Modify: `app/config.py` (add timezone field)
- Modify: `app/utils.py` (add tz param, use zoneinfo)
- Modify: `app/schemas.py:6,24-35` (computed fields use settings.timezone)
- Modify: `app/services/pdf_generator.py:17,310-311` (use settings.timezone)
- Modify: `pyproject.toml` (remove pytz)
- Test: `tests/test_utils.py` (update)
- Test: `tests/test_config.py` (add timezone test)

- [ ] **Step 1: Write failing test for timezone config**

Add to `tests/test_config.py`:
```python
    @patch.dict("os.environ", {"CHURCHTOOLS_BASE": "test.church.tools", "TIMEZONE": "America/New_York"}, clear=False)
    def test_custom_timezone(self):
        from zoneinfo import ZoneInfo
        from app.config import Settings

        s = Settings()
        assert s.timezone == ZoneInfo("America/New_York")

    @patch.dict("os.environ", {"CHURCHTOOLS_BASE": "test.church.tools", "TIMEZONE": "Invalid/Zone"}, clear=False)
    def test_invalid_timezone_raises(self):
        from app.config import Settings

        with self.assertRaises(Exception):
            Settings()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_config.py::TestSettings::test_custom_timezone -v`
Expected: FAIL

- [ ] **Step 3: Add timezone to Settings**

In `app/config.py`, add:
```python
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
```

Add field to `Settings`:
```python
    timezone_name: str = "Europe/Berlin"
```

The correct approach: declare `timezone` as a typed `ZoneInfo` field. Pydantic v2 doesn't support `_timezone` as a non-declared attribute on `BaseSettings`.

Updated `app/config.py` after this step (full file):
```python
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_version() -> str:
    try:
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "0.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        arbitrary_types_allowed=True,
    )

    churchtools_base: str
    db_path: str = "churchtools.db"
    churchtools_base_url: str = ""
    cookie_login_token: str = "login_token"
    version: str = _read_version()
    file_directory: str = str(Path(__file__).parent.parent / "saved_files")  # removed in Task 5
    timezone_name: str = Field(default="Europe/Berlin", validation_alias="TIMEZONE")
    timezone: ZoneInfo = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _set_computed_defaults(self) -> "Settings":
        if not self.churchtools_base_url:
            self.churchtools_base_url = f"https://{self.churchtools_base}"
        try:
            object.__setattr__(self, "timezone", ZoneInfo(self.timezone_name))
        except (ZoneInfoNotFoundError, KeyError) as e:
            raise ValueError(f"Invalid timezone: {self.timezone_name}") from e
        return self


settings = Settings()
```

Key points:
- `arbitrary_types_allowed=True` enables `ZoneInfo` as a field type
- `timezone` is a proper Pydantic field (not a private attr), defaulting to `None` and set in the validator
- `object.__setattr__` is needed because Pydantic models are frozen by default after validation
- `validation_alias="TIMEZONE"` maps the env var `TIMEZONE` to the field `timezone_name`
- `exclude=True` on `timezone` keeps it out of serialization

- [ ] **Step 4: Run timezone config test**

Run: `venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Write failing test for parse_iso_datetime with custom tz**

Add to `tests/test_utils.py`:
```python
from zoneinfo import ZoneInfo

    def test_parse_iso_datetime_custom_timezone(self):
        dt_str = "2023-01-15T14:30:00Z"
        ny_tz = ZoneInfo("America/New_York")
        result = parse_iso_datetime(dt_str, tz=ny_tz)
        self.assertEqual(result.hour, 9)  # 14 UTC = 9 EST
```

- [ ] **Step 6: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_utils.py::TestUtils::test_parse_iso_datetime_custom_timezone -v`
Expected: FAIL — `parse_iso_datetime` doesn't accept `tz` param

- [ ] **Step 7: Update parse_iso_datetime to use zoneinfo**

Rewrite `app/utils.py`:
```python
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo


def parse_iso_datetime(dt_str: str, tz: Optional[ZoneInfo] = None) -> datetime:
    """Converts an ISO datetime string to a timezone-aware datetime."""
    if tz is None:
        from app.config import settings
        tz = settings.timezone

    if dt_str.endswith("Z"):
        dt = datetime.fromisoformat(dt_str.rstrip("Z"))
        utc_dt = dt.replace(tzinfo=timezone.utc)
    else:
        utc_dt = datetime.fromisoformat(dt_str)

    return utc_dt.astimezone(tz)
```

- [ ] **Step 8: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_utils.py -v`
Expected: PASS

- [ ] **Step 9: Update existing test to not use pytz**

In `tests/test_utils.py`, replace:
```python
import pytz
```
with:
```python
from zoneinfo import ZoneInfo
```

Replace `pytz.timezone("Europe/Berlin")` with `ZoneInfo("Europe/Berlin")` in assertions.

- [ ] **Step 10: Update schemas.py computed fields**

No change needed — computed fields call `parse_iso_datetime()` which already defaults to `settings.timezone`.

- [ ] **Step 11: Update pdf_generator.py**

Replace `from app.utils import normalize_newlines, parse_iso_datetime` — already uses it.
In `_draw_event` at line 310-311, `parse_iso_datetime` calls already work since they default to settings.timezone.

- [ ] **Step 12: Remove pytz from pyproject.toml**

Remove `"pytz>=2026.1",` from dependencies.

Run: `venv/bin/pip install -e ".[dev]"`

- [ ] **Step 13: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 14: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`

- [ ] **Step 15: Commit**

```bash
git add app/config.py app/utils.py app/schemas.py app/services/pdf_generator.py pyproject.toml tests/
git commit -m "refactor: migrate from pytz to zoneinfo, make timezone configurable"
```

---

## Chunk 2: Database & Infrastructure

### Task 3: Alembic Migrations

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/001_initial_schema.py`
- Create: `entrypoint.sh`
- Modify: `app/database.py` (remove create_schema)
- Modify: `app/main.py` (remove create_schema call)
- Modify: `Dockerfile`
- Modify: `pyproject.toml` (add alembic dep)
- Test: `tests/test_database.py` (update create_schema test)

- [ ] **Step 1: Add alembic dependency**

In `pyproject.toml`, add to dependencies:
```
    "alembic>=1.15",
```

Run: `venv/bin/pip install -e ".[dev]"`

- [ ] **Step 2: Initialize alembic**

Run: `cd /Users/dsh/repos/privat/churchtools-api && venv/bin/alembic init alembic`

- [ ] **Step 3: Configure alembic.ini**

Edit `alembic.ini`:
- Set `sqlalchemy.url` to empty string (we'll set it programmatically in env.py)
- Set `script_location = alembic`

- [ ] **Step 4: Configure alembic/env.py**

Rewrite `alembic/env.py`:
```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base

import app.models  # noqa: F401 — register models with Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.db_path}")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5: Create initial migration**

Run: `cd /Users/dsh/repos/privat/churchtools-api && CHURCHTOOLS_BASE=placeholder venv/bin/alembic revision --autogenerate -m "initial schema"`

Review the generated migration. It should create all 4 tables. Add `IF NOT EXISTS` guards for existing deployment compatibility:

Edit the generated migration's `upgrade()` to use:
```python
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("additional_info", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_table(
        "color_settings",
        sa.Column("setting_name", sa.String(), nullable=False),
        sa.Column("background_color", sa.String(), nullable=False),
        sa.Column("background_alpha", sa.Integer(), nullable=False),
        sa.Column("date_color", sa.String(), nullable=False),
        sa.Column("description_color", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("setting_name"),
        if_not_exists=True,
    )
    op.create_table(
        "logo_settings",
        sa.Column("setting_name", sa.String(), nullable=False),
        sa.Column("logo_data", sa.LargeBinary(), nullable=True),
        sa.Column("logo_filename", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("setting_name"),
        if_not_exists=True,
    )
    op.create_table(
        "background_image_settings",
        sa.Column("setting_name", sa.String(), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=True),
        sa.Column("image_filename", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("setting_name"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("background_image_settings")
    op.drop_table("logo_settings")
    op.drop_table("color_settings")
    op.drop_table("appointments")
```

- [ ] **Step 6: Remove create_schema from database.py**

Remove the `create_schema()` function from `app/database.py`. Remove the `import app.models` inside it.

- [ ] **Step 7: Remove create_schema call from main.py**

Remove `from app.database import create_schema` and the `create_schema()` call from `app/main.py`.

- [ ] **Step 8: Create entrypoint.sh**

Create `entrypoint.sh`:
```bash
#!/bin/sh
set -e

DB_FILE="${DB_PATH:-/app/data/churchtools.db}"

# Ensure data directory exists
mkdir -p "$(dirname "$DB_FILE")"

# If DB exists with app tables but no alembic_version, stamp it as current
if [ -f "$DB_FILE" ]; then
    HAS_APP_TABLES=$(sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name='color_settings'" 2>/dev/null || true)
    HAS_ALEMBIC=$(sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'" 2>/dev/null || true)

    if [ -n "$HAS_APP_TABLES" ] && [ -z "$HAS_ALEMBIC" ]; then
        echo "Existing database detected without alembic tracking. Stamping as current..."
        alembic stamp head
    fi
fi

# Run migrations
alembic upgrade head

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 5005 "$@"
```

Run: `chmod +x entrypoint.sh`

- [ ] **Step 9: Update Dockerfile**

Add `sqlite3` to runtime deps (for entrypoint detection), copy alembic files, change CMD to entrypoint:

```dockerfile
# Add to runtime apt-get install line:
    sqlite3 \

# After COPY app/ line, add:
COPY alembic/ ./alembic/
COPY alembic.ini entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Replace CMD with:
ENTRYPOINT ["./entrypoint.sh"]
```

- [ ] **Step 10: Update test_database.py**

Remove `test_create_schema` test (function no longer exists). Update import: remove `from app.database import create_schema`.

- [ ] **Step 11: Test migration works on fresh database**

Run:
```bash
cd /Users/dsh/repos/privat/churchtools-api
rm -f test_migration.db
CHURCHTOOLS_BASE=test DB_PATH=test_migration.db venv/bin/alembic upgrade head
sqlite3 test_migration.db ".tables"
rm test_migration.db
```
Expected: Shows all 4 tables + alembic_version

- [ ] **Step 12: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 13: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`

- [ ] **Step 14: Commit**

```bash
git add alembic/ alembic.ini entrypoint.sh app/database.py app/main.py Dockerfile pyproject.toml tests/test_database.py
git commit -m "feat: add Alembic migrations, remove create_schema"
```

---

### Task 4: Shared Async httpx Client

**Files:**
- Modify: `app/main.py` (add lifespan context manager)
- Modify: `app/services/churchtools_client.py` (accept client param)
- Modify: `app/api/appointments.py` (inject client)
- Modify: `app/api/auth.py` (inject client)
- Test: `tests/test_appointments.py` (update mocks)
- Test: `tests/test_auth.py` (update mocks)

- [ ] **Step 1: Write failing test for fetch_calendars with client param**

In `tests/test_appointments.py`, update `test_fetch_calendars_success` — the key change is that we now pass a mock client directly instead of patching `httpx.AsyncClient` context manager:

```python
@pytest.mark.asyncio
async def test_fetch_calendars_success(config_mock):
    client_instance = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "data": [
            {"id": 1, "name": "Calendar 1", "isPublic": True},
            {"id": 2, "name": "Calendar 2", "isPublic": False},
            {"id": 3, "name": "Calendar 3", "isPublic": True},
        ]
    }
    client_instance.get.return_value = response

    result = await fetch_calendars("test_token", client_instance)

    assert len(result) == 2
```

Similarly update `test_fetch_calendars_auth_error`:
```python
@pytest.mark.asyncio
async def test_fetch_calendars_auth_error():
    client_instance = AsyncMock()
    response = MagicMock()
    response.status_code = 401
    client_instance.get.return_value = response

    with pytest.raises(AuthenticationError):
        await fetch_calendars("invalid_token", client_instance)
```

And `test_fetch_appointments`, `test_fetch_appointments_deduplication`, `test_fetch_appointments_partial_failure` — remove the `@patch("httpx.AsyncClient")` decorator, create `client_instance = AsyncMock()` directly, and pass it as the last argument to `fetch_appointments(...)`.

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_appointments.py -v`
Expected: FAIL — `fetch_calendars` doesn't accept client param

- [ ] **Step 3: Update churchtools_client.py**

Modify `fetch_calendars` and `fetch_appointments` to accept a `client: httpx.AsyncClient` parameter:

```python
async def fetch_calendars(login_token: str, client: httpx.AsyncClient):
    url = f"{settings.churchtools_base_url}/api/calendars"
    response = await client.get(url, headers=_auth_headers(login_token))
    # ... rest unchanged, remove async with httpx.AsyncClient() as client:
```

```python
async def fetch_appointments(login_token: str, start_date: str, end_date: str, calendar_ids: List[int], client: httpx.AsyncClient):
    headers = _auth_headers(login_token)
    query_params = {"from": start_date, "to": end_date}
    appointments = []
    seen_ids = set()

    tasks = [_fetch_calendar_appointments(client, cal_id, headers, query_params) for cal_id in calendar_ids]
    results = await asyncio.gather(*tasks)
    # ... rest unchanged, remove async with httpx.AsyncClient() as client:
```

- [ ] **Step 4: Add lifespan context manager to main.py**

```python
from contextlib import asynccontextmanager
import httpx

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    yield
    await app.state.http_client.aclose()

app = FastAPI(title="ChurchTools API", lifespan=lifespan)
```

- [ ] **Step 5: Add dependency function for client injection**

In `app/main.py` or a new `app/dependencies.py`:
```python
from fastapi import Request

def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client
```

- [ ] **Step 6: Update api/appointments.py to inject client**

Add `client: httpx.AsyncClient = Depends(get_http_client)` to route handlers that call churchtools_client functions. Pass `client` to `fetch_calendars` and `fetch_appointments`.

- [ ] **Step 7: Update api/auth.py to inject client**

Same pattern for login and logout routes.

- [ ] **Step 8: Update all tests to mock the shared client**

For tests calling service functions directly (e.g., `fetch_calendars`, `fetch_appointments`): create `client = AsyncMock()` and pass directly.

For tests calling route handlers (e.g., `test_appointments_page_with_token`): the handler now gets client via `Depends(get_http_client)`. Mock by patching the function that resolves the dependency, e.g., `@patch("app.api.appointments.fetch_calendars")` (already mocked — the handler calls `fetch_calendars(login_token, client)` and the mock intercepts).

For `test_auth.py` tests: `login()` and `logout()` now take a `client` param via Depends. Update test calls:
```python
# Before: await login(request_mock, username="testuser", password="testpass")
# After:  await login(request_mock, username="testuser", password="testpass", client=client_mock)
```
Where `client_mock = AsyncMock()` with appropriate response mocking.

Remove all `@patch("httpx.AsyncClient")` decorators — we no longer use context managers.

- [ ] **Step 9: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 10: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`

- [ ] **Step 11: Commit**

```bash
git add app/main.py app/services/churchtools_client.py app/api/ tests/
git commit -m "refactor: shared async httpx client with lifespan management"
```

---

### Task 5: In-Memory PDF/JPEG Generation

**Files:**
- Modify: `app/services/pdf_generator.py:350-389` (BytesIO, return bytes)
- Modify: `app/services/jpeg_generator.py` (accept bytes, use convert_from_bytes)
- Modify: `app/api/appointments.py:158-227,300-311` (StreamingResponse, remove download endpoint)
- Modify: `app/config.py` (remove file_directory field)
- Modify: `app/main.py` (remove FILE_DIRECTORY mkdir)
- Test: `tests/test_pdf_generator.py` (update)

- [ ] **Step 1: Update existing test_create_pdf to expect bytes**

In `tests/test_pdf_generator.py`, the existing `TestPdfGenerator` class has `setUp` that patches `Config.FILE_DIRECTORY` — this must be updated to patch `settings.file_directory` first (from Task 1), then in this step we change `test_create_pdf` to expect bytes:

Remove `self.config_mock` / `self.config_patch` from `setUp`/`tearDown` (no longer needed after in-memory change).

Replace the existing `test_create_pdf` method:
```python
    @patch("app.services.pdf_generator.canvas.Canvas")
    @patch("app.services.pdf_generator.wrap_text")
    @patch("app.services.pdf_generator.pdfmetrics")
    def test_create_pdf(self, mock_pdfmetrics, mock_wrap_text, mock_canvas):
        canvas_instance = MagicMock()
        mock_canvas.return_value = canvas_instance
        mock_wrap_text.return_value = (["Test Event"], 30)
        mock_pdfmetrics.getRegisteredFontNames.return_value = []
        mock_pdfmetrics.stringWidth.return_value = 50

        appointments = [
            AppointmentData(
                id="1_101", title="Test Event",
                start_date="2023-01-15T10:00:00Z", end_date="2023-01-15T12:00:00Z",
                information="Test Info", meeting_at="Test Location", additional_info="Additional Info",
            )
        ]

        with patch("app.services.pdf_generator.parse_iso_datetime") as mock_parse:
            mock_dt = MagicMock()
            mock_dt.strftime.side_effect = lambda fmt: "15.01.2023" if fmt == "%d.%m.%Y" else "11:00"
            mock_parse.return_value = mock_dt
            with patch("app.services.pdf_generator.format_date", return_value="Sonntag"):
                result = create_pdf(appointments, "#c1540c", "#ffffff", "#4e4e4e", 128)

        # After in-memory change: Canvas gets a BytesIO, not a file path
        mock_canvas.assert_called_once()
        args = mock_canvas.call_args[0]
        import io
        assert hasattr(args[0], 'read'), "Canvas should receive a BytesIO buffer"

        # create_pdf now returns bytes
        # With mocked Canvas, buffer.getvalue() returns b'' (empty), which is fine for unit test
        assert isinstance(result, bytes)
        canvas_instance.save.assert_called_once()
        canvas_instance.setTitle.assert_called_once_with("appointments")
```

Also update `test_handle_jpeg_generation` in `tests/test_appointments.py` to pass bytes instead of filename:
```python
@patch("app.services.jpeg_generator.convert_from_bytes")
def test_handle_jpeg_generation(mock_convert):
    mock_image1 = MagicMock()
    mock_image2 = MagicMock()
    mock_convert.return_value = [mock_image1, mock_image2]
    def mock_save(stream, format): stream.write(b"test image data")
    mock_image1.save.side_effect = mock_save
    mock_image2.save.side_effect = mock_save

    result = handle_jpeg_generation(b"%PDF-fake-content")
    mock_convert.assert_called_once_with(b"%PDF-fake-content")
    assert isinstance(result, bytes)
```

Update `test_api_generate_pdf` and `test_api_generate_jpeg`:
- `mock_create_pdf.return_value = b"%PDF-content"` (bytes, not filename)
- `mock_jpeg.return_value = b"PK-zip-content"` (bytes, not filename)
- Response assertions change: no more `download_url` JSON. Instead check `response` is a `StreamingResponse`.

Remove `test_download_file_success`, `test_download_file_not_found`, `test_download_file_path_traversal` (endpoint is removed).

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_pdf_generator.py::TestPdfGenerator::test_create_pdf -v`
Expected: FAIL — `create_pdf` still returns filename string

- [ ] **Step 3: Update pdf_generator.py to use BytesIO**

In `create_pdf()`:
```python
def create_pdf(
    appointments, date_color, background_color, description_color, alpha, image_stream=None, logo_stream=None
) -> bytes:
    font_name, font_name_bold = _register_fonts()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(PAGE_SIZE))
    c.setTitle("appointments")

    # ... rest of drawing code unchanged ...

    c.save()
    logger.info(f"PDF generated with {len(appointments)} appointments")
    return buffer.getvalue()
```

Remove `os` import, `Config`/`settings` import (no longer needed for FILE_DIRECTORY), and filename/file_path construction.

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_pdf_generator.py -v`
Expected: PASS

- [ ] **Step 5: Write failing test for handle_jpeg_generation with bytes input**

```python
def test_handle_jpeg_generation_accepts_bytes(self):
    pdf_bytes = create_pdf([...], "#c1540c", "#d3d3d3", "#4e4e4e", 128)
    result = handle_jpeg_generation(pdf_bytes)
    assert isinstance(result, bytes)
    # Verify it's a valid zip
    import zipfile
    import io
    z = zipfile.ZipFile(io.BytesIO(result))
    assert len(z.namelist()) > 0
```

- [ ] **Step 6: Update jpeg_generator.py**

```python
import logging
import zipfile
from io import BytesIO

from pdf2image import convert_from_bytes

logger = logging.getLogger(__name__)


def handle_jpeg_generation(pdf_bytes: bytes) -> bytes:
    images = convert_from_bytes(pdf_bytes)
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for i, image in enumerate(images):
            jpeg_stream = BytesIO()
            image.save(jpeg_stream, "JPEG")
            zip_file.writestr(f"page_{i + 1}.jpg", jpeg_stream.getvalue())

    logger.info(f"JPEG images generated: {len(images)} pages")
    return zip_buffer.getvalue()
```

- [ ] **Step 7: Run jpeg test**

Run: `venv/bin/python -m pytest tests/test_pdf_generator.py -v`
Expected: PASS

- [ ] **Step 8: Update api/appointments.py — StreamingResponse for generate**

Replace `api_generate` endpoint to return `StreamingResponse`:

```python
from fastapi.responses import StreamingResponse

@router.post("/api/generate")
async def api_generate(request: Request, body: GenerateRequest, db: Session = Depends(get_db)):
    # ... existing auth check and data fetching ...

    pdf_bytes = create_pdf(
        selected_appointments,
        color_settings.date_color,
        color_settings.background_color,
        color_settings.description_color,
        color_settings.background_alpha,
        background_image_stream,
        logo_stream,
    )

    if body.type == "jpeg":
        zip_bytes = handle_jpeg_generation(pdf_bytes)
        return StreamingResponse(
            BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=appointments.zip"},
        )

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=appointments.pdf"},
    )
```

- [ ] **Step 9: Remove download endpoint**

Delete the `@router.get("/download/{filename}")` route and its `download_file` function. Remove `FileResponse` import. Remove `os` import if no longer used.

- [ ] **Step 10: Remove file_directory from Settings**

In `app/config.py`, remove the `file_directory` field. In `app/main.py`, remove the `Path(settings.file_directory).mkdir(...)` line if it exists.

- [ ] **Step 11: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 12: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`

- [ ] **Step 13: Commit**

```bash
git add app/services/ app/api/appointments.py app/config.py app/main.py tests/
git commit -m "refactor: in-memory PDF/JPEG generation with StreamingResponse"
```

---

## Chunk 3: Observability & Security

### Task 6: Health Check Endpoint

**Files:**
- Create: `app/api/health.py`
- Modify: `app/main.py` (include router)
- Modify: `Dockerfile` (HEALTHCHECK)
- Test: `tests/test_health.py` (new)

- [ ] **Step 1: Write failing test**

Create `tests/test_health.py`:
```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_health.py -v`
Expected: FAIL — 404

- [ ] **Step 3: Create health endpoint**

Create `app/api/health.py`:
```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": settings.version})
```

- [ ] **Step 4: Register router in main.py**

```python
from app.api import appointments, auth, health

app.include_router(health.router, tags=["health"])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 6: Add HEALTHCHECK to Dockerfile**

Add before the ENTRYPOINT line:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5005/health')" || exit 1
```

- [ ] **Step 7: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add app/api/health.py app/main.py Dockerfile tests/test_health.py
git commit -m "feat: add /health endpoint with Docker HEALTHCHECK"
```

---

### Task 7: Structured Logging with structlog

**Files:**
- Create: `app/logging_config.py`
- Modify: `app/config.py` (add LOG_FORMAT field)
- Modify: `app/main.py` (configure logging, add request middleware)
- Modify: All modules with `logging.getLogger` (swap to structlog)
- Modify: `pyproject.toml` (add structlog dep)
- Test: `tests/test_logging.py` (new)

- [ ] **Step 1: Add structlog dependency**

In `pyproject.toml`, add:
```
    "structlog>=25.1",
```

Run: `venv/bin/pip install -e ".[dev]"`

- [ ] **Step 2: Write failing test for logging config**

Create `tests/test_logging.py`:
```python
import unittest
from unittest.mock import patch


class TestLoggingConfig(unittest.TestCase):
    def test_configure_logging_console(self):
        from app.logging_config import configure_logging
        configure_logging("console")
        import structlog
        logger = structlog.get_logger()
        assert logger is not None

    def test_configure_logging_json(self):
        from app.logging_config import configure_logging
        configure_logging("json")
        import structlog
        logger = structlog.get_logger()
        assert logger is not None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_logging.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 4: Create logging_config.py**

Create `app/logging_config.py`:
```python
import logging
import sys

import structlog


def configure_logging(log_format: str = "console") -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        # format_exc_info only needed for JSON — ConsoleRenderer handles it internally
        shared_processors.append(structlog.processors.format_exc_info)
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_logging.py -v`
Expected: PASS

- [ ] **Step 6: Add LOG_FORMAT to Settings**

In `app/config.py`, add:
```python
    log_format: str = "console"  # "console" or "json"
```

- [ ] **Step 7: Configure logging in main.py**

At the top of `app/main.py`, before other app imports:
```python
from app.config import settings
from app.logging_config import configure_logging

configure_logging(settings.log_format)
```

- [ ] **Step 8: Replace logging.getLogger with structlog.get_logger**

In each module that uses logging:
- `app/crud.py`: `import structlog; logger = structlog.get_logger()`
- `app/services/churchtools_client.py`: same
- `app/services/pdf_generator.py`: same
- `app/services/jpeg_generator.py`: same
- `app/api/appointments.py`: same

Remove `import logging` where no longer needed.

- [ ] **Step 9: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 10: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`

- [ ] **Step 11: Commit**

```bash
git add app/logging_config.py app/config.py app/main.py app/crud.py app/services/ app/api/ pyproject.toml tests/test_logging.py
git commit -m "feat: structured logging with structlog, configurable format"
```

---

### Task 8: CSRF Protection

**Files:**
- Create: `app/middleware/csrf.py`
- Create: `app/middleware/__init__.py`
- Modify: `app/main.py` (register middleware)
- Modify: Templates (add hidden fields + meta tag)
- Test: `tests/test_csrf.py` (new)

- [ ] **Step 1: Write failing test for CSRF middleware**

Create `tests/test_csrf.py`:
```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.testclient import TestClient


def test_csrf_blocks_post_without_token():
    from app.middleware.csrf import CSRFMiddleware

    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])

    @test_app.post("/test")
    async def test_post():
        return JSONResponse({"ok": True})

    client = TestClient(test_app)
    response = client.post("/test")
    assert response.status_code == 403


def test_csrf_allows_post_with_matching_token():
    from app.middleware.csrf import CSRFMiddleware

    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])

    @test_app.get("/get-token")
    async def get_token(request: Request):
        return HTMLResponse("<html></html>")

    @test_app.post("/test")
    async def test_post():
        return JSONResponse({"ok": True})

    client = TestClient(test_app)
    # First GET to receive csrf cookie
    get_resp = client.get("/get-token")
    csrf_token = get_resp.cookies.get("csrf_token")
    assert csrf_token is not None

    # POST with matching header
    response = client.post("/test", headers={"X-CSRF-Token": csrf_token})
    assert response.status_code == 200


def test_csrf_allows_get_without_token():
    from app.middleware.csrf import CSRFMiddleware

    test_app = FastAPI()
    test_app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])

    @test_app.get("/test")
    async def test_get():
        return JSONResponse({"ok": True})

    client = TestClient(test_app)
    response = client.get("/test")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_csrf.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Create CSRF middleware**

Create `app/middleware/__init__.py` (empty).

Create `app/middleware/csrf.py`:
```python
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exempt_paths: list[str] | None = None):
        super().__init__(app)
        self.exempt_paths = set(exempt_paths or [])

    async def dispatch(self, request: Request, call_next) -> Response:
        # Always set/rotate CSRF token cookie on responses
        if request.method in ("GET", "HEAD", "OPTIONS"):
            response = await call_next(request)
            token = secrets.token_urlsafe(32)
            response.set_cookie(
                "csrf_token",
                token,
                httponly=False,
                samesite="strict",
                secure=request.url.scheme == "https",
            )
            return response

        # For state-changing methods, validate token
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        cookie_token = request.cookies.get("csrf_token")
        if not cookie_token:
            return JSONResponse({"error": "CSRF token missing"}, status_code=403)

        # Check header first (HTMX/AJAX), then form body
        header_token = request.headers.get("X-CSRF-Token")
        if header_token and secrets.compare_digest(header_token, cookie_token):
            return await call_next(request)

        # Check form body
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            form = await request.form()
            form_token = form.get("_csrf_token")
            if form_token and secrets.compare_digest(str(form_token), cookie_token):
                return await call_next(request)

        # Also accept token in JSON body header (for fetch API calls)
        return JSONResponse({"error": "CSRF token mismatch"}, status_code=403)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_csrf.py -v`
Expected: PASS

- [ ] **Step 5: Register middleware in main.py**

```python
from app.middleware.csrf import CSRFMiddleware

app.add_middleware(CSRFMiddleware, exempt_paths=["/health"])
```

- [ ] **Step 5b: Add CSRF hidden field to login form template**

In `app/templates/login.html`, inside the `<form>` that POSTs to `/`, add:
```html
<input type="hidden" name="_csrf_token" value="{{ request.cookies.get('csrf_token', '') }}">
```

The CSRF token cookie is set by the middleware on the GET request that renders the login page. The template reads it from the cookie and embeds it as a hidden field. On POST, the middleware compares the cookie value with the form field.

Similarly add hidden fields to any other forms that POST (logo upload, background upload forms in `appointments.html`).

For the logout form in `appointments.html`, add the same hidden field:
```html
<input type="hidden" name="_csrf_token" value="{{ request.cookies.get('csrf_token', '') }}">
```

- [ ] **Step 6: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: Some tests may fail if they POST without CSRF tokens. Fix by adding CSRF token handling to test helpers.

- [ ] **Step 7: Fix broken tests**

For test clients that POST, add CSRF token flow:
1. GET any page to receive the `csrf_token` cookie
2. Include `X-CSRF-Token: <token>` header on POST requests

- [ ] **Step 8: Run full test suite again**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 9: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`

- [ ] **Step 10: Commit**

```bash
git add app/middleware/ app/main.py tests/test_csrf.py tests/
git commit -m "feat: add CSRF protection middleware (double-submit cookie)"
```

---

### Task 9: Standardized Error Responses

**Files:**
- Modify: `app/schemas.py` (add ErrorResponse)
- Modify: `app/main.py` (exception handlers)
- Modify: `app/api/appointments.py` (consistent errors)
- Modify: `app/api/auth.py` (consistent errors)
- Test: `tests/test_error_responses.py` (new)

- [ ] **Step 1: Write failing test**

Create `tests/test_error_responses.py`:
```python
from app.schemas import ErrorResponse


def test_error_response_model():
    err = ErrorResponse(error="not_found", detail="Resource not found")
    assert err.error == "not_found"
    assert err.detail == "Resource not found"


def test_error_response_without_detail():
    err = ErrorResponse(error="server_error")
    assert err.detail is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_error_responses.py -v`
Expected: FAIL — `ErrorResponse` doesn't exist

- [ ] **Step 3: Add ErrorResponse to schemas.py**

```python
class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_error_responses.py -v`
Expected: PASS

- [ ] **Step 5: Add exception handlers to main.py**

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    return JSONResponse({"error": "unauthorized", "detail": str(exc.detail)}, status_code=401)

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse({"error": "not_found", "detail": str(exc.detail)}, status_code=404)

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc):
    return JSONResponse({"error": "validation_error", "detail": str(exc)}, status_code=422)
```

- [ ] **Step 6: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add app/schemas.py app/main.py tests/test_error_responses.py
git commit -m "feat: standardized error response model and exception handlers"
```

---

## Chunk 4: Code Quality & Cleanup

### Task 10: Pathlib Consistency

**Files:**
- Modify: `app/services/pdf_generator.py:2,4,46,64,74,76,83` (os.path → pathlib)
- Modify: Any remaining `os.path` usage

- [ ] **Step 1: Find all os.path usage**

Search for `os.path` across the codebase. After Tasks 1-5, the remaining usage should be primarily in `pdf_generator.py` (font path resolution).

- [ ] **Step 2: Replace os.path in pdf_generator.py**

Replace:
```python
_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "fonts")
```
With:
```python
_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "fonts"
```

Replace all `os.path.join(_FONTS_DIR, f"{font_name}.ttf")` with `str(_FONTS_DIR / f"{font_name}.ttf")`.

Remove `import os` if no longer used.

- [ ] **Step 3: Replace os.path in any remaining files**

Check all other files for `os.path` usage and convert.

- [ ] **Step 4: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`

- [ ] **Step 6: Commit**

```bash
git add app/
git commit -m "refactor: replace os.path with pathlib throughout"
```

---

### Task 11: Type Hint Completeness

**Files:**
- Modify: `app/crud.py` (add return types)
- Modify: `app/api/auth.py` (add return types)
- Modify: `app/api/appointments.py` (add return types)
- Modify: `app/utils.py` (already typed, verify)

- [ ] **Step 1: Add return types to crud.py**

```python
def save_additional_infos(db: Session, appointment_info_list: list[tuple[str, str]]) -> None:
def get_additional_infos(db: Session, appointment_ids: list[str]) -> dict[str, str]:
def save_color_settings(db: Session, settings: ColorSettings) -> None:
def load_color_settings(db: Session, setting_name: str) -> ColorSettings:
def save_logo(db: Session, setting_name: str, logo_data: bytes, filename: str) -> None:
def load_logo(db: Session, setting_name: str) -> tuple[bytes | None, str | None]:
def delete_logo(db: Session, setting_name: str) -> None:
def save_background_image(db: Session, setting_name: str, image_data: bytes, filename: str) -> None:
def load_background_image(db: Session, setting_name: str) -> tuple[bytes | None, str | None]:
def delete_background_image(db: Session, setting_name: str) -> None:
```

Add `from sqlalchemy.orm import Session` import to crud.py.

- [ ] **Step 2: Add return types to route handlers**

Route handlers return `Response` types — add `-> Response` or specific types like `-> JSONResponse`, `-> RedirectResponse`, `-> TemplateResponse`.

- [ ] **Step 3: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`

- [ ] **Step 5: Commit**

```bash
git add app/crud.py app/api/ app/utils.py
git commit -m "refactor: add complete type annotations"
```

---

## Chunk 5: Multi-Profile Settings

### Task 12: Multi-Profile Settings

**Files:**
- Modify: `app/crud.py` (parameterize setting_name, add profile CRUD)
- Modify: `app/schemas.py` (add profile field to GenerateRequest)
- Modify: `app/api/appointments.py` (accept profile param)
- Modify: `app/main.py` (orphan cleanup in lifespan)
- Test: `tests/test_database.py` (add profile tests)
- Test: `tests/test_profile_crud.py` (new)

- [ ] **Step 1: Write failing tests for profile CRUD**

Create `tests/test_profile_crud.py`:
```python
import os
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base


class TestProfileCRUD(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.engine = create_engine(f"sqlite:///{self.temp_db.name}")
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.session.close()
        os.unlink(self.temp_db.name)

    def test_list_profiles_default_only(self):
        from app.crud import list_profiles, save_color_settings
        from app.schemas import ColorSettings

        save_color_settings(self.session, ColorSettings(name="default"))
        profiles = list_profiles(self.session)
        self.assertEqual(profiles, ["default"])

    def test_list_profiles_multiple(self):
        from app.crud import list_profiles, save_color_settings
        from app.schemas import ColorSettings

        save_color_settings(self.session, ColorSettings(name="default"))
        save_color_settings(self.session, ColorSettings(name="sunday"))
        profiles = list_profiles(self.session)
        self.assertIn("default", profiles)
        self.assertIn("sunday", profiles)

    def test_clone_profile(self):
        from app.crud import clone_profile, load_color_settings, save_color_settings
        from app.schemas import ColorSettings

        save_color_settings(self.session, ColorSettings(name="default", background_color="#ff0000"))
        clone_profile(self.session, "default", "copy")

        result = load_color_settings(self.session, "copy")
        self.assertEqual(result.background_color, "#ff0000")

    def test_delete_profile_default_raises(self):
        from app.crud import delete_profile, save_color_settings
        from app.schemas import ColorSettings

        save_color_settings(self.session, ColorSettings(name="default"))
        with self.assertRaises(ValueError):
            delete_profile(self.session, "default")

    def test_delete_profile_cascades(self):
        from app.crud import delete_profile, list_profiles, save_color_settings, save_logo
        from app.schemas import ColorSettings

        save_color_settings(self.session, ColorSettings(name="temp"))
        save_logo(self.session, "temp", b"logodata", "logo.png")
        delete_profile(self.session, "temp")

        profiles = list_profiles(self.session)
        self.assertNotIn("temp", profiles)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_profile_crud.py -v`
Expected: FAIL — functions don't exist

- [ ] **Step 3: Implement profile CRUD functions in crud.py**

Add to `app/crud.py`:
```python
def list_profiles(db) -> list[str]:
    try:
        results = db.query(ColorSetting.setting_name).distinct().all()
        return [r[0] for r in results]
    except SQLAlchemyError as e:
        logger.error(f"Error listing profiles: {e}")
        return []


def clone_profile(db, source: str, target: str) -> None:
    try:
        # Clone colors
        source_colors = db.query(ColorSetting).filter(ColorSetting.setting_name == source).first()
        if not source_colors:
            raise ValueError(f"Source profile '{source}' does not exist")

        db.add(ColorSetting(
            setting_name=target,
            background_color=source_colors.background_color,
            background_alpha=source_colors.background_alpha,
            date_color=source_colors.date_color,
            description_color=source_colors.description_color,
        ))

        # Clone logo if exists
        source_logo = db.query(LogoSetting).filter(LogoSetting.setting_name == source).first()
        if source_logo:
            db.add(LogoSetting(
                setting_name=target,
                logo_data=source_logo.logo_data,
                logo_filename=source_logo.logo_filename,
            ))

        # Clone background if exists
        source_bg = db.query(BackgroundImageSetting).filter(BackgroundImageSetting.setting_name == source).first()
        if source_bg:
            db.add(BackgroundImageSetting(
                setting_name=target,
                image_data=source_bg.image_data,
                image_filename=source_bg.image_filename,
            ))

        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def delete_profile(db, profile_name: str) -> None:
    if profile_name == "default":
        raise ValueError("Cannot delete the default profile")

    try:
        db.query(BackgroundImageSetting).filter(BackgroundImageSetting.setting_name == profile_name).delete()
        db.query(LogoSetting).filter(LogoSetting.setting_name == profile_name).delete()
        db.query(ColorSetting).filter(ColorSetting.setting_name == profile_name).delete()
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def cleanup_orphaned_settings(db) -> None:
    """Remove logo/background rows with no corresponding color_settings entry."""
    try:
        valid_profiles = {r[0] for r in db.query(ColorSetting.setting_name).all()}
        db.query(LogoSetting).filter(~LogoSetting.setting_name.in_(valid_profiles)).delete(synchronize_session=False)
        db.query(BackgroundImageSetting).filter(
            ~BackgroundImageSetting.setting_name.in_(valid_profiles)
        ).delete(synchronize_session=False)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/bin/python -m pytest tests/test_profile_crud.py -v`
Expected: PASS

- [ ] **Step 5: Add profile field to GenerateRequest**

In `app/schemas.py`:
```python
class GenerateRequest(BaseModel):
    type: Literal["pdf", "jpeg"]
    start_date: str
    end_date: str
    calendar_ids: List[str]
    appointment_ids: List[str]
    color_settings: ColorSettings
    additional_infos: Dict[str, str] = {}
    profile: str = "default"
```

- [ ] **Step 6: Update api_generate to use profile**

In `app/api/appointments.py`, replace `DEFAULT_SETTING_NAME` with `body.profile` for logo/background loading:
```python
    bg_data, _ = load_background_image(db, body.profile)
    logo_data, _ = load_logo(db, body.profile)
```

Add profile existence check:
```python
    from app.crud import list_profiles
    if body.profile not in list_profiles(db):
        raise HTTPException(status_code=404, detail=f"Profile '{body.profile}' not found")
```

- [ ] **Step 7: Add orphan cleanup to lifespan**

In `app/main.py` lifespan:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cleanup orphaned settings on startup
    from app.database import SessionLocal
    from app.crud import cleanup_orphaned_settings
    db = SessionLocal()
    try:
        cleanup_orphaned_settings(db)
    finally:
        db.close()

    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    yield
    await app.state.http_client.aclose()
```

- [ ] **Step 8: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 9: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`

- [ ] **Step 10: Commit**

```bash
git add app/crud.py app/schemas.py app/api/appointments.py app/main.py tests/test_profile_crud.py
git commit -m "feat: multi-profile settings with clone, delete, and orphan cleanup"
```

---

## Chunk 6: Frontend Upgrade (HTMX + Alpine.js)

> **Note:** This is the largest task. It involves replacing ~1300 LOC of vanilla JS with HTMX + Alpine.js. The exact template changes depend heavily on the current template structure. This task should be approached incrementally — one template feature at a time.

### Task 13: HTMX + Alpine.js Frontend

**Files:**
- Create: `app/static/js/htmx.min.js` (download from htmx.org)
- Create: `app/static/js/alpine.min.js` (download from alpinejs.dev)
- Create: `app/api/fragments.py` (fragment response router)
- Create: `app/templates/fragments/appointments.html`
- Create: `app/templates/fragments/settings_panel.html`
- Modify: `app/templates/appointments.html` (add hx-* attributes)
- Modify: `app/templates/login.html` (add CSRF meta tag)
- Modify: `app/main.py` (include fragments router)
- Modify/Remove: `app/static/js/app.js`

- [ ] **Step 1: Download HTMX and Alpine.js**

```bash
curl -o app/static/js/htmx.min.js https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js
curl -o app/static/js/alpine.min.js https://unpkg.com/alpinejs@3.14.8/dist/cdn.min.js
```

- [ ] **Step 2: Create fragments router**

Create `app/api/fragments.py`:
```python
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import DEFAULT_SETTING_NAME, get_db
from app.crud import load_color_settings, load_logo, load_background_image
from app.services.churchtools_client import AuthenticationError, fetch_appointments, parse_appointment
from app.crud import get_additional_infos
from app.shared import templates

logger = structlog.get_logger()
router = APIRouter(prefix="/fragments")


@router.get("/appointments")
async def fragment_appointments(
    request: Request,
    db: Session = Depends(get_db),
    start_date: str = Query(...),
    end_date: str = Query(...),
    calendar_ids: List[str] = Query(...),
):
    login_token = request.cookies.get(settings.cookie_login_token)
    if not login_token:
        return HTMLResponse("<p>Nicht angemeldet</p>", status_code=401)

    calendar_ids_int = [int(cid) for cid in calendar_ids if cid.isdigit()]
    if not calendar_ids_int:
        return HTMLResponse("<p>Keine Kalender ausgewählt</p>")

    client = request.app.state.http_client
    try:
        raw_appointments = await fetch_appointments(login_token, start_date, end_date, calendar_ids_int, client)
    except AuthenticationError:
        return HTMLResponse("<p>Sitzung abgelaufen</p>", status_code=401)

    appointments = [parse_appointment(raw) for raw in raw_appointments]
    additional_infos = get_additional_infos(db, [app.id for app in appointments])
    for appointment in appointments:
        appointment.additional_info = additional_infos.get(appointment.id, "")

    return templates.TemplateResponse(
        "fragments/appointments.html",
        {"request": request, "appointments": appointments},
    )
```

- [ ] **Step 3: Create fragment templates**

Create `app/templates/fragments/appointments.html`:
```html
{% for appointment in appointments %}
<div class="appointment-card" data-id="{{ appointment.id }}">
    <div class="appointment-date">
        {{ appointment.start_date_view }}
    </div>
    <div class="appointment-time">
        {{ appointment.start_time_view }} - {{ appointment.end_time_view }} Uhr
    </div>
    <div class="appointment-title">{{ appointment.title }}</div>
    {% if appointment.meeting_at %}
    <div class="appointment-location">{{ appointment.meeting_at }}</div>
    {% endif %}
    <div class="appointment-info">
        <textarea name="additional_info_{{ appointment.id }}"
                  class="additional-info-input">{{ appointment.additional_info }}</textarea>
    </div>
</div>
{% endfor %}
{% if not appointments %}
<p>Keine Termine gefunden</p>
{% endif %}
```

- [ ] **Step 4: Add HTMX + Alpine.js to base template**

In `app/templates/appointments.html`, add to `<head>`:
```html
<script src="/static/js/htmx.min.js"></script>
<script src="/static/js/alpine.min.js" defer></script>
<meta name="csrf-token" content="{{ csrf_token }}">
<script>
document.addEventListener('htmx:configRequest', function(event) {
    var token = document.querySelector('meta[name="csrf-token"]')?.content;
    if (token) event.detail.headers['X-CSRF-Token'] = token;
});
</script>
```

- [ ] **Step 5: Register fragments router in main.py**

```python
from app.api import appointments, auth, health, fragments

app.include_router(fragments.router, tags=["fragments"])
```

- [ ] **Step 6: Incrementally convert appointment loading to HTMX**

Replace the JS fetch call for loading appointments with an HTMX trigger on the appointment container. This is an incremental process — convert one feature at a time, test, commit.

- [ ] **Step 7: Convert remaining JS features to HTMX/Alpine.js**

Iterate through the remaining vanilla JS features:
- Logo upload/delete → HTMX forms
- Background upload/delete → HTMX forms
- Color picker → Alpine.js state
- Calendar selection → Alpine.js with HTMX trigger

- [ ] **Step 8: Remove replaced vanilla JS code from app.js**

As each feature is converted, remove the corresponding JS function. Eventually most of app.js is replaced.

- [ ] **Step 9: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 10: Run linter**

Run: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`

- [ ] **Step 11: Commit**

```bash
git add app/static/js/ app/api/fragments.py app/templates/ app/main.py
git commit -m "feat: HTMX + Alpine.js frontend upgrade"
```

---

## Final Checklist

After all tasks are complete:

- [ ] Run full test suite: `venv/bin/python -m pytest tests/ -v --cov=app`
- [ ] Run linter: `venv/bin/python -m ruff check . && venv/bin/python -m ruff format --check .`
- [ ] Build Docker image: `podman build -t churchtools-local .`
- [ ] Test Docker container starts and /health returns 200
- [ ] Regenerate requirements.txt from clean install
- [ ] Update README with new env vars (TIMEZONE, LOG_FORMAT)
