The role of this file is to describe common mistakes and confusion points that agents might encounter as they work in this project. If you ever encounter something in the project that surprises you, please alert the developer working with you and indicate that this is the case in the AgentMD file to help prevent future agents from having the same issue.

## Tooling

- Tools and tasks live in `mise.toml` (no Makefile). Use `mise run test`, `mise run lint`, `mise run format`. The venv is `.venv`, auto-activated by mise.
- `requirements.txt` is generated (`mise run lock`) and holds only runtime deps for the Docker image. Declare dependencies in `pyproject.toml`, never edit `requirements.txt` by hand.
- ruff >= 0.16 also formats Python code blocks in Markdown files, so `mise run lint` can fail on `.md` changes.

## Known pitfalls

- Starlette >= 1.0 only accepts `templates.TemplateResponse(request, "name.html", context)`. The old form `TemplateResponse("name.html", {"request": request, ...})` crashes with `TypeError: unhashable type: 'dict'`.
- Most route tests mock `templates`, so they do not catch template or rendering errors. `tests/test_template_rendering.py` renders real pages; extend it when adding pages.
