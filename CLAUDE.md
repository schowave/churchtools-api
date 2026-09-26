The role of this file is to describe common mistakes and confusion points that agents might encounter as they work in this project. If you ever encounter something in the project that surprises you, please alert the developer working with you and indicate that this is the case in the AgentMD file to help prevent future agents from having the same issue.

## Tooling

- Tools and tasks live in `mise.toml` (no Makefile). Use `mise run test`, `mise run lint`, `mise run format`. The venv is `.venv`, auto-activated by mise.
- `requirements.txt` is generated (`mise run lock`) and holds only runtime deps for the Docker image, with hashes (pip verifies them in the Docker build). Declare dependencies in `pyproject.toml`, never edit `requirements.txt` by hand.
- The release workflow builds and scans (trivy) the image before tagging and pushing. Keep that order: Watchtower deploys whatever lands on Docker Hub as `latest`.
- ruff >= 0.16 also formats Python code blocks in Markdown files, so `mise run lint` can fail on `.md` changes.

## Known pitfalls

- Starlette >= 1.0 only accepts `templates.TemplateResponse(request, "name.html", context)`. The old form `TemplateResponse("name.html", {"request": request, ...})` crashes with `TypeError: unhashable type: 'dict'`.
- Most route tests mock `templates`, so they do not catch template or rendering errors. `tests/test_template_rendering.py` renders real pages; extend it when adding pages.
- Login uses server-side sessions (`app/services/sessions.py`, table `login_sessions`): the `session` cookie holds a random id, the ChurchTools token stays in the DB, Fernet-encrypted with a key derived from the session id (only the sha256 of the id is stored). Without the cookie the DB cannot decrypt a token, so any code that needs the token must have the session id. Never put the token itself into a cookie or a response.
- `tests/conftest.py` also mocks the session store (session id == token) unless a test is marked `@pytest.mark.real_sessions`.
- New Alembic migrations: `entrypoint.sh` stamps pre-alembic databases as `001`, never `head`, so later migrations still run.
- Pages send a strict CSP (`script-src 'self'`, see `app/main.py`). No inline `<script>` blocks or `on*=` handlers in templates; `tests/test_template_rendering.py` enforces it. Put behaviour into the page's JS file.
- ChurchTools does not reject invalid login tokens: `/api/whoami` (and likely other endpoints) answers with HTTP 200 as the anonymous user (`id: -1`). A cookie being present, or a ChurchTools call succeeding, proves nothing. Protected routes must use `get_valid_login_token` / `require_auth` from `app/services/auth.py`, which checks `id > 0`.
- `tests/conftest.py` has an autouse fixture that treats every login token as valid. Tests for the real validation opt out with `@pytest.mark.real_token_validation`.
- Uploaded images are validated with Pillow (PNG/JPEG only) and served with a content type sniffed from the bytes. Never derive the content type from the stored filename.
- The Termin-Folien, Agenda and Dienstplan pages share `render_calendar_page` in `app/api/calendar_pages.py`. Tests that mock `fetch_calendars`, `get_date_range_from_form` or `templates` for these pages must patch `app.api.calendar_pages.*`, not the route modules.
- PDF/JPEG generation is CPU-bound (JPEG shells out to pdftoppm): call it via `run_in_threadpool`, never directly in an async route, or the whole server stalls during exports.
- Log with structlog events and fields (`logger.info("pdf_created", appointments=n)`), not f-strings.
- The runtime image has no pip (removed in the Dockerfile; trivy flagged its vendored packages). Install-time steps belong in the builder stage.
- Resolve files inside the package from `APP_DIR` (`app/config.py`), never from relative paths like `"app/static"`: those break when the process starts outside the repo root. Fonts for the PDFs live in `app/resources/fonts/`.
- Tests mirror `app/` (`tests/api/`, `tests/services/`, `tests/services/pdf/`, `tests/middleware/`); cross-cutting tests (security, template rendering, error handling) stay in `tests/`. Shared fixtures such as `config_mock` live in `tests/conftest.py`.
- Logo and background routes live in `app/api/images.py`; tests must patch `app.api.images.*` for them, while `/api/generate` still reads images via `app.api.appointments.*`.
- The HTTP client is `httpx2` (maintained continuation of httpx by pydantic, same API). Do not re-add `httpx`.
- Appointment ids are `{calendar_id}_{base.id}_{startDate}`; custom texts (`appointments` table) are stored under them. Never make the id depend on the requested date range or list position. Texts saved under the old ids (`{calendar}_{base}[_{n}]`) are migrated lazily on load (`legacy_appointment_ids` + `claim_legacy_additional_infos`); keep that path until old installations have been used once.
- State-changing requests from JS go through `csrfFetch` (`appointments.js`): it reads the token from the cookie (the meta tag can be stale on mobile) and retries once on `csrf_failed`. Plain `fetch` with a CSRF header breaks on long-open pages.
- The container starts as root only so `entrypoint.sh` can chown the data volume, then re-executes itself as user `app` via `setpriv`. Keep root-only steps before that point.
- ReportLab `Paragraph` parses its text as markup, including `<img src="...">`, which reads local files and fetches URLs. Put ChurchTools or user text into PDFs only via `text_paragraph` (`app/services/pdf/markup.py`), never via `Paragraph` directly.
- Endpoints that forward a date range or calendar ids to ChurchTools must bound them: `GenerateRequest` validates itself, query endpoints call `check_range_query` (`app/web.py`). `/api/generate` stores custom texts only for appointment ids ChurchTools returned for the user.
- Logged-in pages include `_nav.html` via `{% with active="<page>" %}{% include "_nav.html" %}{% endwith %}`; new pages must do the same (a test checks it). Logout lives on `/profile` only; after login users land on `/appointments` (`START_PAGE` in `app/api/auth.py`), `/overview` only redirects there.
- Colors: text tokens in `common.css` meet WCAG AA (4.5:1); form controls use `--input-border` (3:1), `--border-color` is decorative only. Keep pinch-zoom enabled (no `user-scalable=no`/`maximum-scale` in the viewport meta).
- Fonts are self-hosted (`app/static/css/fonts.css`, `app/static/fonts/`). Never link Google Fonts or other third-party font/CDN URLs: that sends visitors' IPs to the provider (GDPR); a test enforces it and the CSP only allows `'self'`.
- Access can be limited with `ALLOWED_GROUP_IDS` / `ALLOWED_PERSON_IDS` (`has_app_access` in `app/services/auth.py`, called from `validate_login_token`). Both empty must keep allowing every ChurchTools login, or a Watchtower deploy locks everyone out.
- The installed version is only shown on the profile page; keep it out of `/health` and the login page.
