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
- Add `alembic upgrade head` to Docker entrypoint so migrations run automatically on container startup
- Future schema changes ship as migration files in the container

### Files affected
- New: `alembic/`, `alembic.ini`
- Modified: `Dockerfile` (entrypoint), `pyproject.toml` (dependency)

---

## 2. Frontend Upgrade: HTMX + Alpine.js

### Problem
~1300 LOC of vanilla JavaScript handling form submissions, dynamic loading, and UI updates. Hard to maintain and extend.

### Design
- Add HTMX (14kb gzipped) for server-driven interactivity:
  - Appointment loading via `hx-get="/api/appointments"`
  - PDF/JPEG generation with `hx-post` and `hx-indicator` for progress
  - Logo/background upload and delete without full page reload
  - Partial page updates via HTML fragment responses
- Add Alpine.js (17kb gzipped) for client-side reactive state:
  - Color picker state and live preview
  - Calendar selection checkboxes
  - Form validation and conditional UI
- Both served from `static/` (no CDN dependency)
- Server-side: add HTML fragment response endpoints alongside existing JSON endpoints
- Gradually replace vanilla JS functions with declarative HTML attributes

### Files affected
- New: `static/js/htmx.min.js`, `static/js/alpine.min.js`
- Modified: All 3 Jinja2 templates (add hx-* and x-* attributes)
- Modified: `api/appointments.py` (fragment response endpoints)
- Removed: Most of `static/js/app.js` (replaced by declarative attributes)

---

## 3. In-Memory PDF/JPEG Generation

### Problem
Generated PDFs/JPEGs are written to disk and never cleaned up. Files accumulate indefinitely.

### Design
- Modify `pdf_generator.py` to write to `io.BytesIO` instead of file paths
- Modify `jpeg_generator.py` to accept bytes input and return bytes (BytesIO for zip archives)
- Return `StreamingResponse` directly from the generate endpoint
- Remove the `/download/{filename}` endpoint
- Remove `output/` directory management

### Benefits
- No temp files, no cleanup needed
- No path traversal concerns
- Lower disk I/O
- Memory usage bounded (single PDF typically <5MB)

### Files affected
- Modified: `services/pdf_generator.py`, `services/jpeg_generator.py`
- Modified: `api/appointments.py` (StreamingResponse instead of file redirect)
- Removed: Download endpoint, output directory logic

---

## 4. Configurable Timezone

### Problem
Timezone hardcoded to `Europe/Berlin` throughout the codebase.

### Design
- Add `TIMEZONE` environment variable (default: `Europe/Berlin`)
- Validate timezone string at startup (must be valid pytz timezone)
- Replace all `pytz.timezone("Europe/Berlin")` calls with config-driven value
- Document in README

### Files affected
- Modified: `config.py` (or new pydantic settings), `utils.py`, `schemas.py`
- Modified: `README.md`, `docker-compose.yml` (document new env var)

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
- New profiles can be created by cloning an existing profile or starting fresh

### Database changes (Alembic migration)
- No schema change needed - `setting_name` primary key already supports multiple values
- Just remove the hardcoded `"default"` constraint in CRUD operations

### Files affected
- Modified: `crud.py` (parameterize setting_name, add list/create/delete profile operations)
- Modified: `api/appointments.py` (accept profile parameter)
- Modified: `templates/appointments.html` (profile selector dropdown)
- Modified: `schemas.py` (add profile-related schemas)

---

## 6. CSRF Protection

### Problem
POST forms have no CSRF protection. Relies solely on SameSite cookie policy.

### Design
- Implement lightweight CSRF middleware (~30 LOC, no new dependency)
- Generate random token per session, store in HTTPOnly cookie
- Embed token in forms as hidden `<input>` field
- Validate token on all POST/PUT/DELETE requests
- Exempt API endpoints that use Authorization header (they're not vulnerable to CSRF)

### Files affected
- New: `middleware/csrf.py`
- Modified: `main.py` (register middleware)
- Modified: All Jinja2 templates with forms (add hidden CSRF field)

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
- ChurchTools client functions accept the client as a parameter instead of creating their own

### Files affected
- Modified: `main.py` (add lifespan context manager)
- Modified: `services/churchtools_client.py` (accept client parameter)
- Modified: `api/appointments.py`, `api/auth.py` (inject client via Depends)

---

## 9. Structured Logging with structlog

### Problem
Logging is unstructured plain text, hard to parse and analyze.

### Design
- Add `structlog` dependency
- Configure JSON output format with stdlib integration
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
- Validated fields: `CHURCHTOOLS_BASE` (str, required), `DB_PATH` (Path, default), `TIMEZONE` (str, validated), `CHURCHTOOLS_BASE_URL` (computed)
- `pydantic-settings` is already a transitive dependency of FastAPI

### Files affected
- Modified: `config.py` (rewrite as BaseSettings)
- Modified: Modules importing Config (minimal changes - API stays similar)

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
| structlog | Structured logging | ~500KB |
| htmx.min.js | Server-driven interactivity | 14KB gzipped |
| alpine.min.js | Reactive client state | 17KB gzipped |

`pydantic-settings` is already a transitive dependency and doesn't need explicit addition.

---

## Testing Strategy

- Each improvement gets its own test additions
- Existing tests updated to match new patterns (e.g., mock shared client instead of per-request client)
- New tests for: CSRF middleware, health endpoint, profile CRUD, structured log output format
- Migration tests: verify upgrade/downgrade paths
