# AJAX-Based PDF/JPEG Generation — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace native HTML form POST with AJAX JSON requests for PDF/JPEG generation, fixing deployment issues through Cloudflare Tunnel where appointment selection and transparency settings are ignored.

**Architecture:** New `POST /api/generate` JSON endpoint replaces the old form-based `POST /appointments` flow. Frontend collects form data via JavaScript and sends JSON, matching the existing AJAX pattern used by `fetchAppointmentsAjax()`. Old form-based handlers are removed.

**Tech Stack:** FastAPI (Python), Pydantic models, jQuery/vanilla JS, Jinja2 templates

**Spec:** `docs/superpowers/specs/2026-03-14-ajax-generation-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app/schemas.py` | Modify | Add `GenerateRequest` Pydantic model, default `ColorSettings.name` |
| `app/api/appointments.py` | Modify | Add `POST /api/generate`, remove old form handlers |
| `app/static/js/appointments.js` | Modify | Replace form-submit with AJAX `generateOutput()` |
| `app/templates/appointments.html` | Modify | Buttons from `type="submit"` to `type="button"`, replace `<form>` with `<div>` |
| `tests/test_appointments.py` | Modify | Add tests for new endpoint, remove old form-POST tests |
| `tests/test_schemas.py` | Modify | Add tests for `GenerateRequest` validation |

---

## Chunk 1: Backend — Request Model + New Endpoint

### Task 1: Add GenerateRequest Pydantic model

**Files:**
- Modify: `app/schemas.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Write tests for GenerateRequest validation**

Add to the end of `tests/test_schemas.py`:

```python
from app.schemas import GenerateRequest


def test_generate_request_valid():
    req = GenerateRequest(
        type="pdf",
        start_date="2026-03-14",
        end_date="2026-03-21",
        calendar_ids=["1", "2"],
        appointment_ids=["1_101", "2_102"],
        color_settings={
            "background_color": "#ffffff",
            "background_alpha": 128,
            "date_color": "#c1540c",
            "description_color": "#4e4e4e",
        },
        additional_infos={"1_101": "Some info", "2_102": ""},
    )
    assert req.type == "pdf"
    assert req.appointment_ids == ["1_101", "2_102"]
    assert req.additional_infos["1_101"] == "Some info"
    assert req.color_settings.name == "default"  # from new default


def test_generate_request_invalid_type():
    import pytest
    with pytest.raises(ValueError):
        GenerateRequest(
            type="png",
            start_date="2026-03-14",
            end_date="2026-03-21",
            calendar_ids=["1"],
            appointment_ids=["1_101"],
            color_settings={
                "background_color": "#ffffff",
                "background_alpha": 128,
                "date_color": "#c1540c",
                "description_color": "#4e4e4e",
            },
            additional_infos={},
        )


def test_generate_request_empty_appointments():
    import pytest
    with pytest.raises(ValueError):
        GenerateRequest(
            type="pdf",
            start_date="2026-03-14",
            end_date="2026-03-21",
            calendar_ids=["1"],
            appointment_ids=[],
            color_settings={
                "background_color": "#ffffff",
                "background_alpha": 128,
                "date_color": "#c1540c",
                "description_color": "#4e4e4e",
            },
            additional_infos={},
        )


def test_generate_request_defaults_additional_infos():
    req = GenerateRequest(
        type="jpeg",
        start_date="2026-03-14",
        end_date="2026-03-21",
        calendar_ids=["1"],
        appointment_ids=["1_101"],
        color_settings={
            "background_color": "#ffffff",
            "background_alpha": 128,
            "date_color": "#c1540c",
            "description_color": "#4e4e4e",
        },
    )
    assert req.additional_infos == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_schemas.py -v -k "generate_request"`
Expected: FAIL — `ImportError: cannot import name 'GenerateRequest'`

- [ ] **Step 3: Implement GenerateRequest model**

Two changes in `app/schemas.py`:

**Change 1:** Add imports at the top of the file. The existing imports are:
```python
import re
from pydantic import BaseModel, computed_field, field_validator
from app.utils import parse_iso_datetime
```

Add `typing` imports below:
```python
from typing import Dict, List, Literal
```

**Change 2:** Give `ColorSettings.name` a default value. Change:
```python
    name: str
```
to:
```python
    name: str = "default"
```

This is needed because `GenerateRequest.color_settings` receives JSON without a `name` field — the Pydantic coercion from dict to `ColorSettings` will use this default.

**Change 3:** Add the `GenerateRequest` class after `ColorSettings`:

```python
class GenerateRequest(BaseModel):
    """JSON request body for PDF/JPEG generation."""

    type: Literal["pdf", "jpeg"]
    start_date: str
    end_date: str
    calendar_ids: List[str]
    appointment_ids: List[str]
    color_settings: ColorSettings
    additional_infos: Dict[str, str] = {}

    @field_validator("appointment_ids")
    @classmethod
    def validate_appointment_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one appointment must be selected")
        return v
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_schemas.py -v -k "generate_request"`
Expected: All 4 tests PASS

- [ ] **Step 5: Run all existing tests to check no regressions**

Run: `pytest tests/test_schemas.py -v`
Expected: All tests PASS (existing callers pass `name="default"` explicitly)

- [ ] **Step 6: Commit**

```bash
git add app/schemas.py tests/test_schemas.py
git commit -m "feat: add GenerateRequest model for AJAX-based generation"
```

---

### Task 2: Add POST /api/generate endpoint

**Files:**
- Modify: `app/api/appointments.py`
- Test: `tests/test_appointments.py`

- [ ] **Step 1: Write tests for the new endpoint**

In `tests/test_appointments.py`:

**Update the imports** on line 9. Change:
```python
from app.api.appointments import appointments_page, download_file, process_appointments
```
to:
```python
from app.api.appointments import api_generate, appointments_page, download_file, process_appointments
```

**Add the import** for `GenerateRequest` below line 10:
```python
from app.schemas import AppointmentData, ColorSettings, GenerateRequest
```

**Add these tests** at the end of the file:

```python
# --- Tests for POST /api/generate (AJAX endpoint) ---


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.appointments.create_pdf")
@patch("app.api.appointments.save_color_settings")
@patch("app.api.appointments.save_additional_infos")
@patch("app.api.appointments.fetch_appointments")
async def test_api_generate_pdf(
    mock_fetch_app,
    mock_save_info,
    mock_save_color,
    mock_create_pdf,
    mock_load_logo,
    mock_load_bg,
    config_mock,
):
    """POST /api/generate with type=pdf should return download URL."""
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "test_token"
    db = MagicMock()

    mock_fetch_app.return_value = SAMPLE_APPOINTMENT_DATA
    mock_create_pdf.return_value = "2023-01-15_Termine.pdf"

    body = GenerateRequest(
        type="pdf",
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_ids=["1_101"],
        color_settings={
            "background_color": "#0000ff",
            "background_alpha": 100,
            "date_color": "#ff0000",
            "description_color": "#00ff00",
        },
        additional_infos={"1_101": "Extra info"},
    )

    response = await api_generate(request=request, body=body, db=db)

    assert response.status_code == 200
    import json
    data = json.loads(response.body)
    assert data["download_url"] == "/download/2023-01-15_Termine.pdf"

    # Verify PDF was created with correct color settings
    # create_pdf signature: (appointments, date_color, background_color, description_color, alpha, image_stream, logo_stream)
    mock_create_pdf.assert_called_once()
    call_args = mock_create_pdf.call_args
    assert call_args[0][1] == "#ff0000"   # date_color
    assert call_args[0][2] == "#0000ff"   # background_color
    assert call_args[0][3] == "#00ff00"   # description_color
    assert call_args[0][4] == 100         # alpha

    # Verify additional infos were saved
    mock_save_info.assert_called_once()
    save_args = mock_save_info.call_args[0]
    assert save_args[1] == [("1_101", "Extra info")]

    # Verify color settings were saved with name="default"
    mock_save_color.assert_called_once()
    saved_cs = mock_save_color.call_args[0][1]
    assert saved_cs.name == "default"


@pytest.mark.asyncio
@patch("app.api.appointments.load_background_image", return_value=(None, None))
@patch("app.api.appointments.load_logo", return_value=(None, None))
@patch("app.api.appointments.handle_jpeg_generation")
@patch("app.api.appointments.create_pdf")
@patch("app.api.appointments.save_color_settings")
@patch("app.api.appointments.save_additional_infos")
@patch("app.api.appointments.fetch_appointments")
async def test_api_generate_jpeg(
    mock_fetch_app,
    mock_save_info,
    mock_save_color,
    mock_create_pdf,
    mock_jpeg,
    mock_load_logo,
    mock_load_bg,
    config_mock,
):
    """POST /api/generate with type=jpeg should return ZIP download URL."""
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "test_token"
    db = MagicMock()

    mock_fetch_app.return_value = SAMPLE_APPOINTMENT_DATA
    mock_create_pdf.return_value = "2023-01-15_Termine.pdf"
    mock_jpeg.return_value = "2023-01-15_Termine.zip"

    body = GenerateRequest(
        type="jpeg",
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_ids=["1_101"],
        color_settings={
            "background_color": "#ffffff",
            "background_alpha": 128,
            "date_color": "#c1540c",
            "description_color": "#4e4e4e",
        },
        additional_infos={},
    )

    response = await api_generate(request=request, body=body, db=db)

    assert response.status_code == 200
    import json
    data = json.loads(response.body)
    assert data["download_url"] == "/download/2023-01-15_Termine.zip"
    mock_jpeg.assert_called_once_with("2023-01-15_Termine.pdf")


@pytest.mark.asyncio
async def test_api_generate_no_auth():
    """POST /api/generate without token should return 401."""
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = None
    db = MagicMock()

    body = GenerateRequest(
        type="pdf",
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_ids=["1_101"],
        color_settings={
            "background_color": "#ffffff",
            "background_alpha": 128,
            "date_color": "#c1540c",
            "description_color": "#4e4e4e",
        },
        additional_infos={},
    )

    response = await api_generate(request=request, body=body, db=db)
    assert response.status_code == 401


@pytest.mark.asyncio
@patch("app.api.appointments.fetch_appointments")
async def test_api_generate_auth_error_mid_session(
    mock_fetch_app,
    config_mock,
):
    """If fetch_appointments raises AuthenticationError, should return 401."""
    request = MagicMock(spec=Request)
    request.cookies.get.return_value = "expired_token"
    db = MagicMock()

    mock_fetch_app.side_effect = AuthenticationError()

    body = GenerateRequest(
        type="pdf",
        start_date="2023-01-15",
        end_date="2023-01-22",
        calendar_ids=["1"],
        appointment_ids=["1_101"],
        color_settings={
            "background_color": "#ffffff",
            "background_alpha": 128,
            "date_color": "#c1540c",
            "description_color": "#4e4e4e",
        },
        additional_infos={},
    )

    response = await api_generate(request=request, body=body, db=db)
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_appointments.py -v -k "api_generate"`
Expected: FAIL — `ImportError: cannot import name 'api_generate'`

- [ ] **Step 3: Implement the POST /api/generate endpoint**

In `app/api/appointments.py`:

**Update the schemas import** (line 24). Change:
```python
from app.schemas import ColorSettings
```
to:
```python
from app.schemas import ColorSettings, GenerateRequest
```

**Add the new endpoint** after the `api_appointments` function. Insert it right after the closing of `api_appointments` (find `return JSONResponse({"appointments":...})` and add after it):

```python
@router.post("/api/generate")
async def api_generate(
    request: Request,
    body: GenerateRequest,
    db: Session = Depends(get_db),
):
    """JSON endpoint for PDF/JPEG generation."""
    login_token = request.cookies.get(Config.COOKIE_LOGIN_TOKEN)
    if not login_token:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    color_settings = body.color_settings

    # Save additional infos to DB
    appointment_info_list = [
        (app_id, normalize_newlines(body.additional_infos.get(app_id, "")))
        for app_id in body.appointment_ids
    ]
    save_additional_infos(db, appointment_info_list)
    save_color_settings(db, color_settings)

    # Load background image and logo from DB
    background_image_stream = None
    bg_data, _ = load_background_image(db, DEFAULT_SETTING_NAME)
    if bg_data:
        background_image_stream = BytesIO(bg_data)

    logo_stream = None
    logo_data, _ = load_logo(db, DEFAULT_SETTING_NAME)
    if logo_data:
        logo_stream = BytesIO(logo_data)

    # Fetch appointments from ChurchTools API
    calendar_ids_int = [int(cid) for cid in body.calendar_ids if cid.isdigit()]
    try:
        raw_appointments = await fetch_appointments(
            login_token, body.start_date, body.end_date, calendar_ids_int
        )
    except AuthenticationError:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)

    appointments = [parse_appointment(raw) for raw in raw_appointments]

    # Assign additional info from request body
    for appointment in appointments:
        appointment.additional_info = body.additional_infos.get(appointment.id, "")

    # Filter to selected appointments
    selected_ids = set(body.appointment_ids)
    selected_appointments = [app for app in appointments if app.id in selected_ids]

    # Preserve order from request
    id_order = {app_id: idx for idx, app_id in enumerate(body.appointment_ids)}
    selected_appointments.sort(key=lambda app: id_order.get(app.id, 0))

    logger.info(f"Generating {body.type}: {len(selected_appointments)} of {len(appointments)} appointments")

    # Generate PDF
    filename = create_pdf(
        selected_appointments,
        color_settings.date_color,
        color_settings.background_color,
        color_settings.description_color,
        color_settings.background_alpha,
        background_image_stream,
        logo_stream,
    )

    # Convert to JPEG if requested
    if body.type == "jpeg":
        filename = handle_jpeg_generation(filename)

    return JSONResponse({"download_url": f"/download/{filename}"})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_appointments.py -v -k "api_generate"`
Expected: All 4 new tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/api/appointments.py tests/test_appointments.py
git commit -m "feat: add POST /api/generate JSON endpoint for PDF/JPEG"
```

---

## Chunk 2: Frontend — AJAX Submit + Template Cleanup

### Task 3: Replace form-submit with AJAX generateOutput()

**Files:**
- Modify: `app/static/js/appointments.js`

- [ ] **Step 1: Replace generate button click handlers and remove monitorDownload**

In `app/static/js/appointments.js`, make three edits:

**Edit 1:** Delete the `monitorDownload()` function. Find:
```javascript
function monitorDownload(cookieName, $btn) {
```
Delete from that line through the closing `}` of the function (the entire function body including the `setInterval`, `clearInterval`, `CustomEvent` dispatch).

**Edit 2:** Add the `generateOutput()` function. Insert it right before the line `// --- jQuery-dependent initialization ---`:

```javascript
function generateOutput(type) {
    var appointmentIds = [];
    $('.appointment-checkbox:checked').each(function () {
        appointmentIds.push($(this).val());
    });

    if (appointmentIds.length === 0) {
        $('#generate_error').text('Bitte mindestens einen Termin auswählen.').show();
        return;
    }
    $('#generate_error').hide();

    var additionalInfos = {};
    appointmentIds.forEach(function (id) {
        var textarea = $('textarea[name="additional_info_' + id + '"]');
        if (textarea.length && textarea.val().trim()) {
            additionalInfos[id] = textarea.val();
        }
    });

    var calendarIds = [];
    $('.calendar-checkbox:checked').each(function () {
        calendarIds.push($(this).val());
    });

    var payload = {
        type: type,
        start_date: $('#start_date').val(),
        end_date: $('#end_date').val(),
        calendar_ids: calendarIds,
        appointment_ids: appointmentIds,
        color_settings: {
            background_color: $('#background_color').val(),
            background_alpha: parseInt($('#alpha').val(), 10),
            date_color: $('#date_color').val(),
            description_color: $('#description_color').val()
        },
        additional_infos: additionalInfos
    };

    var $btn = type === 'pdf' ? $('#generate_pdf_btn') : $('#generate_jpeg_btn');
    showButtonSpinner($btn);

    fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(function (res) {
        if (res.status === 401) {
            window.location.href = '/';
            return;
        }
        if (!res.ok) throw new Error('Fehler beim Generieren');
        return res.json();
    })
    .then(function (data) {
        if (!data) return;
        // Trigger file download (browser stays on page for file responses)
        window.location.href = data.download_url;
        // Reset button after short delay to allow download to start
        $btn.removeClass('is-loading');
        $btn.find('.btn-label').show();
        $btn.find('.btn-spinner').hide();
    })
    .catch(function (err) {
        $('#generate_error').text(err.message).show();
        $btn.removeClass('is-loading');
        $btn.find('.btn-label').show();
        $btn.find('.btn-spinner').hide();
    });
}
```

**Edit 3:** In the jQuery `$(function () { ... })` block, find the generate button click handlers:
```javascript
    // Inline spinner for generate button clicks
    $('#generate_jpeg_btn').click(function () {
        var $btn = $(this);
        showButtonSpinner($btn);
        monitorDownload('jpegGenerated', $btn);
    });

    $('#generate_pdf_btn').click(function () {
        var $btn = $(this);
        showButtonSpinner($btn);
        monitorDownload('pdfGenerated', $btn);
    });
```

Replace with:
```javascript
    // Generate buttons — AJAX, no form submit
    $('#generate_pdf_btn').click(function () {
        generateOutput('pdf');
    });

    $('#generate_jpeg_btn').click(function () {
        generateOutput('jpeg');
    });
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/appointments.js
git commit -m "feat: replace form-submit with AJAX generateOutput()"
```

---

### Task 4: Update HTML template

**Files:**
- Modify: `app/templates/appointments.html`

- [ ] **Step 1: Change form tag and button types**

In `app/templates/appointments.html`, make three edits:

**Edit 1:** Find `<form method="POST">` and replace with `<div class="appointments-form">`.

**Edit 2:** Find the corresponding `</form>` (near the end, before `<footer>`) and replace with `</div>`.

**Edit 3:** Find the PDF generate button:
```html
<button type="submit" name="generate_pdf" value="1" class="btn btn-generate" id="generate_pdf_btn" disabled>
```
Replace with:
```html
<button type="button" class="btn btn-generate" id="generate_pdf_btn" disabled>
```

**Edit 4:** Find the JPEG generate button:
```html
<button type="submit" name="generate_jpeg" value="1" class="btn btn-generate" id="generate_jpeg_btn" disabled>
```
Replace with:
```html
<button type="button" class="btn btn-generate" id="generate_jpeg_btn" disabled>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/appointments.html
git commit -m "feat: remove form POST, change generate buttons to type=button"
```

---

## Chunk 3: Cleanup — Remove Old Handlers + Update Tests

### Task 5: Remove old code and old tests together

**Important:** Remove old backend code and old tests in the same step to avoid a commit with failing tests.

**Files:**
- Modify: `app/api/appointments.py`
- Modify: `tests/test_appointments.py`

- [ ] **Step 1: Remove old backend functions**

In `app/api/appointments.py`, remove these four functions (find by name, not line number — line numbers have shifted since Task 2):

1. **`_prepare_selected_appointments()`** — the `async def` that takes `request, db, login_token, appointment_id, ...` and calls `await request.form()`. Replaced by inline logic in `api_generate`.
2. **`_handle_generate_pdf()`** — the `async def` that calls `_prepare_selected_appointments` and `create_pdf`, returns `RedirectResponse`.
3. **`_handle_generate_jpeg()`** — the `async def` that calls `_prepare_selected_appointments`, `create_pdf`, and `handle_jpeg_generation`, returns `RedirectResponse`.
4. **`process_appointments()`** — the `@router.post("/appointments")` handler with all its `Form()` parameters.

Also update the imports:
- **Remove `Form`** from the `fastapi` import on line 7. The updated import should be:
  ```python
  from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
  ```
  (`Form` is no longer used — logo/background uploads use `File`/`UploadFile`, not `Form`)

- [ ] **Step 2: Remove old tests**

In `tests/test_appointments.py`:

1. **Update imports on line 9.** Remove `process_appointments` since it no longer exists:
   ```python
   from app.api.appointments import api_generate, appointments_page, download_file
   ```

2. **Delete the `_make_request_mock` helper function** (find `def _make_request_mock`). It was only used by the old `process_appointments` tests.

3. **Delete these test functions** (find by function name):
   - `test_process_appointments_no_token`
   - `test_process_appointments_generate_pdf`
   - `test_process_appointments_generate_pdf_no_selection`
   - `test_process_appointments_generate_jpeg`
   - `test_process_appointments_default_form`
   - `test_process_appointments_default_dates`

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/api/appointments.py tests/test_appointments.py
git commit -m "refactor: remove old form-based POST handler and its tests"
```

---

### Task 6: Final verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Test locally**

Run: `uvicorn app.main:app --host 0.0.0.0 --port 5005`

Manual test checklist:
1. Open http://localhost:5005, log in
2. Fetch appointments
3. Uncheck some appointments
4. Change transparency slider
5. Click "PDF generieren" — should download PDF with only selected appointments
6. Click "JPEG generieren" — should download ZIP with only selected appointments
7. Verify transparency is applied correctly in the PDF

- [ ] **Step 3: Commit any fixes from manual testing**

If needed — otherwise skip.
