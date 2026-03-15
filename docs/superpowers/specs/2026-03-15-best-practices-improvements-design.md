# ChurchTools API - Best Practices Improvements Design

**Date:** 2026-03-15
**Status:** Approved
**Scope:** Targeted fixes + selected structural improvements

## Context

ChurchTools API is a FastAPI application for viewing and exporting ChurchTools calendar appointments as PDFs/JPEGs. It's a solo-maintained project deployed by multiple users via Docker. The app is well-structured but has accumulated areas where modern best practices would improve reliability, maintainability, and developer experience.

### Constraints

- Keep SQLite as the database
- Keep single-container Docker deployment
- Minimize new dependencies
- Solo maintainer - changes must be independently valuable and incrementally deliverable

---

## 1. Database Migrations with Alembic

### Problem
Schema changes require manual database recreation, risking data loss for deployed instances.

### Design
- Add `alembic` dependency
- Initialize `alembic/` directory with `env.py` configured to use existing `database.py` engine and `Base.metadata`
- Create initial migration from current 4 models (appointments, color_settings, logo_settings, background_image_settings)
- **Remove `create_schema()`** from `database.py` and its call in `main.py`. Alembic owns all schema management. Using both `create_all()` and Alembic creates a race condition where tables may be created outside Alembic's tracking.
- **Handle existing deployments:** The initial migration uses `op.execute()` with an `IF NOT EXISTS` guard on each `CREATE TABLE`, so it is idempotent. Additionally, `entrypoint.sh` runs `alembic stamp head` if the alembic_version table does not exist but application tables do (detected via `sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='color_settings'" | grep -q color_settings`). This stamps the database as current without running DDL. Execution order in entrypoint.sh: (1) detect existing tables → stamp if needed, (2) `alembic upgrade head`, (3) exec uvicorn.
- Add `entrypoint.sh` shell script with the above logic. Replace Dockerfile CMD with this entrypoint.
- Future schema changes ship as migration files in the container

### Files affected
- New: `alembic/`, `alembic.ini`, `entrypoint.sh`
- Modified: `database.py` (remove `create_schema()`), `main.py` (remove `create_schema()` call)
- Modified: `Dockerfile` (COPY entrypoint.sh, use as ENTRYPOINT), `pyproject.toml` (dependency)

---

## 2. Frontend Upgrade: HTMX + Alpine.js

### Problem
~1300 LOC of vanilla JavaScript handling form submissions, dynamic loading, and UI updates. Hard to maintain and extend.

### Design
- Add HTMX (14kb gzipped) for server-driven interactivity:
  - Appointment loading via `hx-get="/fragments/appointments"`
  - PDF/JPEG generation with `hx-post="/fragments/generate"` and `hx-indicator` for progress
  - Logo/background upload and delete without full page reload
  - Partial page updates via HTML fragment responses
- Add Alpine.js (17kb gzipped) for client-side reactive state:
  - Color picker state and live preview
  - Calendar selection checkboxes
  - Form validation and conditional UI
- Both served from `static/` (no CDN dependency)
- Gradually replace vanilla JS functions with declarative HTML attributes

### Fragment endpoints
HTMX requires HTML responses. New `/fragments/*` endpoints return HTML fragments; existing `/api/*` JSON endpoints remain unchanged for programmatic access.

- `GET /fragments/appointments?calendars=1,2&from=...&to=...` — returns rendered appointment list HTML
- `GET /fragments/settings-panel?profile=...` — returns settings form HTML for the given profile
- `POST /fragments/generate` — generates the PDF/JPEG in-memory, then returns an HTML fragment containing a JavaScript-triggered download. The fragment uses `HX-Trigger` response header to emit a custom event, and a small Alpine.js handler creates a temporary `<a>` element with a `blob:` URL from the binary data. Alternatively (simpler): the fragment returns `<a href="/api/generate?..." download>` — i.e., the `/api/generate` JSON endpoint is kept as a direct binary download endpoint (returns `StreamingResponse`), and the HTMX fragment simply renders a download link pointing to it. **Chosen approach:** Keep `/api/generate` as a direct `StreamingResponse` download endpoint (not HTMX-driven). The generate button uses a regular `<a>` or `<form>` submission (not `hx-post`) so the browser handles the download natively. HTMX is NOT used for the generate action — only for the other fragment endpoints above.
- `DELETE /fragments/logo?profile=...` / `DELETE /fragments/background?profile=...` — returns empty replacement HTML after deletion

These endpoints use Jinja2's `{% block %}` partials extracted from main templates into `templates/fragments/`.

### CSRF token delivery for HTMX
HTMX requests (especially DELETE) don't submit form bodies, so the hidden `<input>` CSRF approach doesn't work for all methods. Instead, set a global HTMX request header via `<meta name="csrf-token" content="{{ csrf_token }}">` in the base template and `document.addEventListener('htmx:configRequest', ...)` to add `X-CSRF-Token` header to all HTMX requests. The CSRF middleware (section 6) accepts the token from either the form body or the `X-CSRF-Token` header.

### Files affected
- New: `static/js/htmx.min.js`, `static/js/alpine.min.js`
- New: `templates/fragments/` directory with partial templates
- New: `api/fragments.py` (fragment response router)
- Modified: All 3 Jinja2 templates (add hx-* and x-* attributes, extract reusable blocks, add CSRF meta tag)
- Removed: Most of `static/js/app.js` (replaced by declarative attributes)

---

## 3. In-Memory PDF/JPEG Generation

### Problem
Generated PDFs/JPEGs are written to disk and never cleaned up. Files accumulate indefinitely.

### Design
- Modify `pdf_generator.py`: `create_pdf()` writes to `io.BytesIO` instead of a file path. The ReportLab `Canvas` constructor accepts a file-like object. **New signature:** `create_pdf(...) -> bytes` (calls `buffer.getvalue()` before returning). Remove the `filename`/`file_path` construction logic. Replace `canvas.Canvas(file_path, ...)` with `canvas.Canvas(buffer, ...)` where `buffer = io.BytesIO()`. Replace `c.setTitle(filename)` with `c.setTitle("appointments")` (static title).
- Modify `jpeg_generator.py`: `handle_jpeg_generation()` accepts `pdf_bytes: bytes` instead of a filename string. **New signature:** `handle_jpeg_generation(pdf_bytes: bytes, ...) -> bytes` (returns zip archive bytes). Replace `pdf2image.convert_from_path()` with `pdf2image.convert_from_bytes(pdf_bytes)`.
- Modify `api_generate` in `api/appointments.py`: call chain becomes `pdf_bytes = create_pdf(...)` → `StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=appointments.pdf"})`. For JPEG: `zip_bytes = handle_jpeg_generation(pdf_bytes, ...)` → `StreamingResponse(io.BytesIO(zip_bytes), media_type="application/zip", headers={"Content-Disposition": "attachment; filename=appointments.zip"})`.
- Remove the `/download/{filename}` endpoint entirely
- Remove `output/` directory management

### Benefits
- No temp files, no cleanup needed
- No path traversal concerns
- Lower disk I/O
- Memory usage bounded (single PDF typically <5MB)

### Files affected
- Modified: `services/pdf_generator.py` (new return type: `bytes`)
- Modified: `services/jpeg_generator.py` (new parameter: `bytes`, new return: `bytes`)
- Modified: `api/appointments.py` (`api_generate` uses StreamingResponse, remove download endpoint)
- Removed: Output directory logic

---

## 4. Configurable Timezone

### Problem
Timezone hardcoded to `Europe/Berlin` throughout the codebase.

### Design
- Add `TIMEZONE` environment variable (default: `Europe/Berlin`)
- Migrate from `pytz` to Python 3.12 stdlib `zoneinfo` module. Validate timezone at startup using `zoneinfo.ZoneInfo(tz)` (raises `zoneinfo.ZoneInfoNotFoundError`, a subclass of `KeyError`, for invalid zones).
- Replace all `pytz.timezone("Europe/Berlin")` calls with config-driven `zoneinfo.ZoneInfo` value
- **Timezone threading:** The configured timezone is stored as a `ZoneInfo` instance on the settings singleton. `parse_iso_datetime` in `utils.py` accepts an optional `tz` parameter, defaulting to `settings.timezone`. For `AppointmentData` computed fields in `schemas.py`: these Pydantic `@computed_field` properties access the settings singleton directly (`from app.config import settings; settings.timezone`). This is acceptable because the timezone is immutable after startup and the settings singleton is configured before any request processing.
- Remove `pytz` dependency
- Document in README

### Files affected
- Modified: `config.py` (add TIMEZONE field with ZoneInfo type), `utils.py` (add tz param to parse_iso_datetime), `schemas.py` (computed fields use settings.timezone), `services/pdf_generator.py`
- Modified: `README.md`, `docker-compose.yml` (document new env var)
- Modified: `pyproject.toml` (remove pytz dependency)

---

## 5. Multi-Profile Settings

### Problem
Settings hardcoded to single "default" profile. No way to have different presets for different use cases.

### Design
- Change `setting_name` from hardcoded `"default"` to user-selectable profiles
- Add CRUD operations for listing, creating, deleting profiles
- Add UI dropdown in the dashboard to switch between profiles
- Each profile stores its own: colors (4 values + alpha), logo, background image
- Default profile always exists and cannot be deleted
- New profiles can be created from scratch (empty colors/no logo/no background) or by cloning an existing profile
- **Cloning behavior:** Cloning copies color values directly. Logo and background image blobs are duplicated into new rows (not shared references), so each profile is fully independent. This is acceptable because profiles are few (typically 2-5) and blobs are capped at 10MB each. Clone operations are wrapped in a single DB transaction — if any part fails, the entire clone is rolled back, preventing orphaned rows.
- **Cross-table consistency:** There is no separate "profiles" table. A profile exists if it has a row in `color_settings`. Logo and background are optional per profile. CRUD operations for delete-profile cascade across all three tables in a single transaction. The profile list is derived from `SELECT DISTINCT setting_name FROM color_settings`. A consistency check in the FastAPI lifespan context manager (introduced in Section 8) removes any orphaned logo/background rows that lack a corresponding color_settings entry at startup.
- **`additional_info` scope:** The `appointments` table stores user-added annotations keyed by appointment ID only. `additional_info` is NOT profile-scoped — it is global across all profiles. This is intentional: the annotation describes the appointment itself, not its visual presentation. No schema change needed for the appointments table.
- **Clone implementation:** The current `crud.py` commits after each individual save operation. The clone operation requires a new `clone_profile(db, source, target)` function that performs all inserts before calling `db.commit()`, ensuring atomicity.
- **Generate endpoint:** Add optional `profile` field to `GenerateRequest` schema (default: `"default"`). The `api_generate` function uses this to load the correct colors, logo, and background for the selected profile. If the requested profile does not exist, return a 404 error (do not silently fall back to default).

### Database changes (Alembic migration)
- No schema change needed - `setting_name` primary key already supports multiple values
- Just remove the hardcoded `"default"` constraint in CRUD operations

### Files affected
- Modified: `crud.py` (parameterize setting_name, add list/create/delete/clone profile operations)
- Modified: `api/appointments.py` (accept profile parameter in generate)
- Modified: `schemas.py` (add `profile` field to `GenerateRequest`, add profile-related schemas)
- Modified: `templates/appointments.html` (profile selector dropdown)

---

## 6. CSRF Protection

### Problem
POST forms have no CSRF protection. Relies solely on SameSite cookie policy.

### Design
Use the **stateless double-submit cookie pattern** (no server-side session store needed):

- On first request, middleware generates a random CSRF token and sets it in two places:
  1. A **non-HTTPOnly** cookie named `csrf_token` (so JavaScript/HTMX can read it)
  2. The Jinja2 template context (available as `{{ csrf_token }}`)
- For **traditional form submissions:** embed token as hidden `<input name="_csrf_token">` field
- For **HTMX/AJAX requests:** a `<meta name="csrf-token">` tag in the base template provides the token value. An `htmx:configRequest` event listener reads the meta tag and adds `X-CSRF-Token` header to all HTMX requests.
- **Validation:** On POST/PUT/DELETE, middleware compares the cookie value against either the form field `_csrf_token` or the `X-CSRF-Token` header. If they match, the request proceeds. An attacker on a different origin cannot read the cookie to set the header/form field.
- Token is rotated on each response (new random value in cookie + template).
- Exempt the `/health` endpoint (no state mutation)

### Files affected
- New: `middleware/csrf.py`
- Modified: `main.py` (register middleware)
- Modified: All Jinja2 templates with forms (add hidden CSRF field + meta tag for HTMX)

---

## 7. Health Check Endpoint

### Problem
No way for Docker or reverse proxies to check if the app is healthy.

### Design
- Add `GET /health` endpoint returning `{"status": "ok", "version": "x.y.z"}`
- Optionally check database connectivity (SQLite file accessible)
- Add `HEALTHCHECK` instruction to Dockerfile
- No authentication required

### Files affected
- Modified: `main.py` or new `api/health.py`
- Modified: `Dockerfile` (HEALTHCHECK instruction)

---

## 8. Shared Async httpx Client

### Problem
`httpx.AsyncClient` created per-request without proper lifecycle management. No connection pooling.

### Design
- Create `httpx.AsyncClient` once at app startup via FastAPI's lifespan context manager
- Configure connection pool limits and timeouts
- Store in `app.state` and inject via `Depends()`
- Close cleanly on shutdown
- Both `fetch_calendars` and `fetch_appointments` in `churchtools_client.py` currently create their own `async with httpx.AsyncClient()` — both need updating to accept a `client: httpx.AsyncClient` parameter. The internal `_fetch_calendar_appointments` helper already accepts a client parameter and requires no changes.

### Files affected
- Modified: `main.py` (add lifespan context manager)
- Modified: `services/churchtools_client.py` (update `fetch_calendars` and `fetch_appointments` signatures)
- Modified: `api/appointments.py`, `api/auth.py` (inject client via Depends)

---

## 9. Structured Logging with structlog

### Problem
Logging is unstructured plain text, hard to parse and analyze.

### Design
- Add `structlog` dependency
- Configure with stdlib integration. Add `LOG_FORMAT` env var with options `console` (default, human-readable colored output — matches current behavior so existing deployments are not disrupted) and `json` (structured, machine-parseable for log aggregation).
- Add context fields: request_id (UUID per request), operation name
- Add request logging middleware (method, path, status, duration)
- Replace `logging.getLogger()` calls with `structlog.get_logger()`

### Files affected
- New: `logging_config.py`
- Modified: `main.py` (configure structlog at startup)
- Modified: All modules using logging (swap to structlog)
- New dependency: `structlog`

---

## 10. Pathlib Consistency

### Problem
Mix of `os.path` and `pathlib.Path` usage across the codebase.

### Design
- Replace all `os.path.join()`, `os.path.basename()`, `os.path.exists()` etc. with `pathlib.Path` equivalents
- Use `Path.resolve()` for path safety where applicable

### Files affected
- Modified: Any module using `os.path` (config, generators, download endpoints)

---

## 11. Type Hint Completeness

### Problem
Some functions missing return type annotations, especially in `crud.py` and route handlers.

### Design
- Add return type annotations to all public functions
- Use `Optional[]`, `list[]`, `dict[]` etc. as appropriate
- Add `-> None` for void functions
- Ensure mypy or pyright could pass (not adding as CI check, just improving the annotations)

### Files affected
- Modified: `crud.py`, `api/auth.py`, `api/appointments.py`, `utils.py`

---

## 12. Pydantic Settings for Configuration

### Problem
Manual `Config` class with `os.environ.get()` calls. No type coercion, no `.env` file support.

### Design
- Replace `Config` class with `pydantic-settings` `BaseSettings` subclass
- Automatic environment variable reading with type validation
- `.env` file support via `model_config = SettingsConfigDict(env_file=".env")`
- Validated fields: `CHURCHTOOLS_BASE` (str, required), `DB_PATH` (Path, default), `TIMEZONE` (str, validated)
- `CHURCHTOOLS_BASE_URL`: Keep as an overridable env var with a default computed from `CHURCHTOOLS_BASE` using a `@model_validator`. This preserves the current behavior where users can override the full URL if needed (e.g., custom domains, HTTP instead of HTTPS).
- **Import-time config:** `database.py` currently reads `Config.DB_PATH` at module level. With `BaseSettings`, the settings instance is also created at import time, which is fine. Remove `load_dotenv()` from `main.py` since `BaseSettings` with `env_file=".env"` handles `.env` loading at instantiation time. Create a module-level `settings = Settings()` instance in `config.py` that all other modules import.
- `pydantic-settings` must be added as an explicit dependency (it is NOT a transitive dependency of FastAPI)

### Files affected
- Modified: `config.py` (rewrite as BaseSettings, export `settings` singleton)
- Modified: `main.py` (remove `load_dotenv()` and `Config.validate()` calls)
- Modified: `pyproject.toml` (add pydantic-settings dependency)
- Modified: Modules importing Config (change to `from app.config import settings`)

---

## 13. Standardized Error Responses

### Problem
Error responses vary across endpoints (some return JSON, some redirect, some raise HTTPException with different formats).

### Design
- Define `ErrorResponse` Pydantic model: `{"error": str, "detail": str | None}`
- Use consistently across all API endpoints
- Add FastAPI exception handlers for common cases (401, 404, 500)
- Document error format in OpenAPI schema

### Files affected
- Modified: `schemas.py` (add ErrorResponse)
- Modified: `main.py` (exception handlers)
- Modified: `api/appointments.py`, `api/auth.py` (consistent error returns)

---

## Implementation Order

Recommended order to minimize conflicts and build on each change:

1. **Pydantic Settings** (config foundation for everything else)
2. **Configurable timezone** (uses new config)
3. **Alembic migrations** (schema foundation)
4. **Multi-profile settings** (uses Alembic for any needed migration)
5. **Shared async httpx client** (infra improvement)
6. **In-memory PDF/JPEG generation** (removes file management)
7. **Structured logging** (observability)
8. **Health check endpoint** (quick win)
9. **CSRF protection** (security)
10. **Pathlib consistency** (cleanup)
11. **Type hint completeness** (cleanup)
12. **Standardized error responses** (API consistency)
13. **HTMX + Alpine.js frontend** (largest change, done last to build on stable backend)

---

## New Dependencies

| Package | Purpose | Size |
|---------|---------|------|
| alembic | Database migrations | ~2MB |
| pydantic-settings | Typed configuration from env vars | ~200KB |
| structlog | Structured logging | ~500KB |
| htmx.min.js | Server-driven interactivity | 14KB gzipped |
| alpine.min.js | Reactive client state | 17KB gzipped |

### Removed Dependencies

| Package | Reason |
|---------|--------|
| pytz | Replaced by stdlib `zoneinfo` (Python 3.12+) |

---

## Testing Strategy

- Each improvement gets its own test additions
- Existing tests updated to match new patterns (e.g., mock shared client instead of per-request client)
- New tests for: CSRF middleware, health endpoint, profile CRUD, structured log output format
- Migration tests: verify upgrade/downgrade paths
