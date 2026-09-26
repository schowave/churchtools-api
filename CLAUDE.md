The role of this file is to describe common mistakes and confusion points that agents might encounter as they work in this project. If you ever encounter something in the project that surprises you, please alert the developer working with you and indicate that this is the case in the AgentMD file to help prevent future agents from having the same issue.

## Tooling

- Tools and tasks live in `mise.toml` (no Makefile). Use `mise run test`, `mise run lint`, `mise run format`. The venv is `.venv`, auto-activated by mise.
- `requirements.txt` is generated (`mise run lock`) and holds only runtime deps for the Docker image, with hashes (pip verifies them in the Docker build). Declare dependencies in `pyproject.toml`, never edit `requirements.txt` by hand.
- The release workflow builds and scans (trivy) the image before tagging and pushing. Keep that order: Watchtower deploys whatever lands on Docker Hub as `latest`.
- ruff >= 0.16 also formats Python code blocks in Markdown files, so `mise run lint` can fail on `.md` changes.

## Known pitfalls

- Starlette >= 1.0 only accepts `templates.TemplateResponse(request, "name.html", context)`. The old form `TemplateResponse("name.html", {"request": request, ...})` crashes with `TypeError: unhashable type: 'dict'`.
- Most route tests mock `templates`, so they do not catch template or rendering errors. `tests/test_template_rendering.py` renders real pages; extend it when adding pages.
- ChurchTools does not reject invalid login tokens: `/api/whoami` (and likely other endpoints) answers with HTTP 200 as the anonymous user (`id: -1`). A cookie being present, or a ChurchTools call succeeding, proves nothing. Protected routes must use `get_valid_login_token` / `_require_auth` from `app/services/auth.py`, which checks `id > 0`.
- `tests/conftest.py` has an autouse fixture that treats every login token as valid. Tests for the real validation opt out with `@pytest.mark.real_token_validation`.
- Uploaded images are validated with Pillow (PNG/JPEG only) and served with a content type sniffed from the bytes. Never derive the content type from the stored filename.
- The Termin-Folien, Agenda and Dienstplan pages share `render_calendar_page` in `app/api/calendar_pages.py`. Tests that mock `fetch_calendars`, `get_date_range_from_form` or `templates` for these pages must patch `app.api.calendar_pages.*`, not the route modules.
- PDF/JPEG generation is CPU-bound (JPEG shells out to pdftoppm): call it via `run_in_threadpool`, never directly in an async route, or the whole server stalls during exports.
- Log with structlog events and fields (`logger.info("pdf_created", appointments=n)`), not f-strings.
- The runtime image has no pip (removed in the Dockerfile; trivy flagged its vendored packages). Install-time steps belong in the builder stage.
