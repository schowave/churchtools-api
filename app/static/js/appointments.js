/* appointments.js — Vanilla JS (no jQuery) */

const $ = (s, c = document) => c.querySelector(s);
const $$ = (s, c = document) => c.querySelectorAll(s);

// --- CSRF token helper ---

// The cookie is the current token; the meta tag can be stale when a mobile browser restores a
// tab after dropping its cookies (any request then sets a new cookie).
function getCsrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
    if (match) return decodeURIComponent(match[1]);
    var meta = $('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

// fetch() for state-changing requests. On a CSRF rejection it fetches a fresh token cookie
// (any GET sets one) and retries once, so an old open page just works instead of showing an error.
function csrfFetch(url, options) {
    function send() {
        var headers = Object.assign({}, options.headers, { 'X-CSRF-Token': getCsrfToken() });
        return fetch(url, Object.assign({}, options, { headers: headers }));
    }
    return send().then(function (res) {
        if (res.status !== 403) return res;
        return res.clone().json().then(function (data) {
            if (!data || data.error !== 'csrf_failed') return res;
            return fetch('/health', { cache: 'no-store' }).then(send);
        }, function () { return res; });
    });
}

// --- Error helpers ---

// Builds a readable error for a failed response. Proxies answer with HTML pages
// (e.g. 502 while the container restarts), so the body is only used when it is JSON.
function responseError(res, fallback) {
    var contentType = res.headers.get('Content-Type') || '';
    if (contentType.indexOf('application/json') === -1) {
        return Promise.resolve(new Error(statusMessage(res.status, fallback)));
    }
    return res.json().then(function (data) {
        // "detail" carries the German message of HTTPExceptions; "error" is only a machine code.
        var detail = typeof data.detail === 'string' ? data.detail : '';
        return new Error(detail || statusMessage(res.status, fallback));
    }, function () {
        return new Error(statusMessage(res.status, fallback));
    });
}

function statusMessage(status, fallback) {
    if (status === 502 || status === 503 || status === 504) {
        return 'Server gerade nicht erreichbar (HTTP ' + status + '). Bitte gleich nochmal versuchen.';
    }
    if (status === 413) return 'Datei zu groß.';
    return fallback + ' (HTTP ' + status + ')';
}

// fetch() rejects with a TypeError when the server cannot be reached at all.
function errorText(err) {
    if (err instanceof TypeError) return 'Server nicht erreichbar. Bitte Verbindung prüfen und nochmal versuchen.';
    return err.message;
}

// --- Utility functions ---

function showButtonSpinner(btn) {
    btn.classList.add('is-loading');
    var label = $('.btn-label', btn);
    var spinner = $('.btn-spinner', btn);
    if (label) label.style.display = 'none';
    if (spinner) spinner.style.display = '';
}

function hideButtonSpinner(btn) {
    btn.classList.remove('is-loading');
    var label = $('.btn-label', btn);
    var spinner = $('.btn-spinner', btn);
    if (label) label.style.display = '';
    if (spinner) spinner.style.display = 'none';
}

function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.max(textarea.scrollHeight, 56) + 'px';
}

function calculateThisWeekDates() {
    var today = new Date();
    var dayOfWeek = today.getDay();

    var daysUntilNextSunday = (0 - dayOfWeek) % 7;
    var nextSunday;
    if (daysUntilNextSunday === 0) {
        nextSunday = new Date(today);
    } else {
        nextSunday = new Date(today);
        nextSunday.setDate(today.getDate() + daysUntilNextSunday + 7);
    }

    var nextNextSunday = new Date(nextSunday);
    nextNextSunday.setDate(nextSunday.getDate() + 7);

    return { start: nextSunday, end: nextNextSunday };
}

function calculateNextWeekDates() {
    var thisWeek = calculateThisWeekDates();

    var nextWeekStart = new Date(thisWeek.start);
    nextWeekStart.setDate(nextWeekStart.getDate() + 7);

    var nextWeekEnd = new Date(thisWeek.end);
    nextWeekEnd.setDate(nextWeekEnd.getDate() + 7);

    return { start: nextWeekStart, end: nextWeekEnd };
}

// Escapes for both text content and quoted attribute values.
// (textContent/innerHTML would leave quotes intact and allow attribute injection.)
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatDateWithWeekday(dateStr) {
    var parts = dateStr.split('.');
    if (parts.length !== 3) return dateStr;
    var date = new Date(parts[2], parts[1] - 1, parts[0]);
    var days = ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'];
    return days[date.getDay()] + ', ' + dateStr;
}

// --- Flatpickr helpers ---

function setDateRange(startDate, endDate) {
    if (window._fpStart) window._fpStart.setDate(startDate, true);
    if (window._fpEnd) window._fpEnd.setDate(endDate, true);
}

function formatIso(date) {
    var y = date.getFullYear();
    var m = String(date.getMonth() + 1).padStart(2, '0');
    var d = String(date.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + d;
}

// --- Appointment rendering ---

var PENCIL_ICON = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/>' +
    '<path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>';

function formatShortDate(isoDate) {
    var parts = isoDate.slice(0, 10).split('-');
    return parts[2] + '.' + parts[1] + '.';
}

function renderTimeColumn(app) {
    if (app.all_day) {
        var multiDay = app.end_date.slice(0, 10) !== app.start_date.slice(0, 10);
        return '<span class="all-day-label">ganztägig</span>' +
            (multiDay ? '<span class="time-end">bis ' + escapeHtml(formatShortDate(app.end_date)) + '</span>' : '');
    }
    return '<span class="time-start">' + escapeHtml(app.start_time_view) + '</span>' +
        '<span class="time-end">' + escapeHtml(app.end_time_view) + '</span>';
}

function openCustomTextEditor(item) {
    var textarea = item.querySelector('textarea');
    item.classList.add('is-editing');
    textarea.classList.remove('hidden');
    autoResizeTextarea(textarea);
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
}

function closeCustomTextEditor(item) {
    var textarea = item.querySelector('textarea');
    var text = textarea.value.trim();
    item.classList.remove('is-editing');
    item.classList.toggle('has-custom-text', text.length > 0);
    item.querySelector('.appointment-custom-text').textContent = text;
    textarea.classList.add('hidden');
}

// "dd.mm.yyyy" -> day header: bold weekday, date, and a badge for today/tomorrow
function renderDateHeader(dateStr) {
    var parts = dateStr.split('.');
    var date = new Date(parts[2], parts[1] - 1, parts[0]);
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var dayDiff = Math.round((date - today) / 86400000);
    var badge = dayDiff === 0 ? 'Heute' : (dayDiff === 1 ? 'Morgen' : '');
    var weekday = formatDateWithWeekday(dateStr).split(',')[0];
    return '<div class="date-group-header">' +
        '<span class="date-weekday">' + escapeHtml(weekday) + '</span>, ' + escapeHtml(dateStr) +
        (badge ? ' <span class="date-badge">' + badge + '</span>' : '') +
        '</div>';
}

// Loaded appointments by id, for the slide preview
var appointmentsById = {};

function renderAppointments(appointments) {
    var main = $('.appointments-main');
    appointmentsById = {};

    if (!appointments || appointments.length === 0) {
        main.innerHTML =
            '<div class="empty-state">' +
                '<p>Keine Termine in diesem Zeitraum.</p>' +
                '<p class="empty-state-hint">Wähle einen anderen Zeitraum oder weitere Kalender.</p>' +
            '</div>';
        updateSelectionState();
        return;
    }

    var html = '<div class="appointments-actions">' +
        '<label class="select-all">' +
            '<input type="checkbox" id="select_all" checked>' +
            '<span class="appointment-count"></span>' +
        '</label>' +
        '</div>' +
        '<div class="appointments-container">';

    var lastDate = null;
    var itemIndex = 0;
    appointments.forEach(function (app) {
        appointmentsById[app.id] = app;
        var dateKey = app.start_date_view;
        if (dateKey !== lastDate) {
            html += renderDateHeader(dateKey);
            lastDate = dateKey;
        }
        var customText = (app.additional_info || '').trim();
        var hasDescription = app.information && app.information.trim().length > 0;
        var delay = Math.min(itemIndex * 0.03, 0.6);
        var checkboxId = 'appointment-' + escapeHtml(app.id);
        html += '<div class="appointment-item' + (customText ? ' has-custom-text' : '') + '" style="animation-delay:' + delay + 's">' +
            '<input type="checkbox" id="' + checkboxId + '" name="appointment_id"' +
                ' value="' + escapeHtml(app.id) + '" class="appointment-checkbox" checked>' +
            '<span class="appointment-time" data-action="toggle-select" aria-hidden="true">' + renderTimeColumn(app) + '</span>' +
            '<div class="appointment-body">' +
                '<label for="' + checkboxId + '" class="appointment-title">' + escapeHtml(app.title) +
                    '<span class="sr-only">, ' + escapeHtml(slideTimeText(app)) + '</span></label>' +
                (hasDescription
                    ? '<p class="appointment-info-text" data-action="toggle-expand" title="Klicken zum Auf-/Zuklappen">' +
                        escapeHtml(app.information) + '</p>'
                    : '') +
                '<p class="appointment-custom-text" data-action="edit-custom-text" title="Eigenen Text bearbeiten">' +
                    escapeHtml(customText) + '</p>' +
                '<textarea name="additional_info_' + escapeHtml(app.id) + '" class="hidden" rows="2" maxlength="2000"' +
                    ' aria-label="Eigener Text für ' + escapeHtml(app.title) + '"' +
                    ' placeholder="Eigener Text – ersetzt die Beschreibung auf der Folie">' + escapeHtml(customText) + '</textarea>' +
            '</div>' +
            '<button type="button" class="custom-text-btn" data-action="edit-custom-text"' +
                ' aria-label="Eigenen Text bearbeiten" title="Eigener Text">' + PENCIL_ICON + '</button>' +
            '</div>';
        itemIndex++;
    });

    html += '</div>';
    main.innerHTML = html;

    updateSelectionState();
}

// Filters reload the list automatically. Changes arrive in bursts (a preset sets both dates),
// so loads are debounced, and answers to superseded requests are dropped.
var fetchTimer = null;
var fetchSequence = 0;

function scheduleFetch(delay) {
    clearTimeout(fetchTimer);
    fetchTimer = setTimeout(fetchAppointmentsAjax, delay === undefined ? 400 : delay);
}

function showListMessage(title, hint, withRetry) {
    appointmentsById = {};
    $('.appointments-main').innerHTML =
        '<div class="empty-state">' +
            '<p>' + escapeHtml(title) + '</p>' +
            (hint ? '<p class="empty-state-hint">' + escapeHtml(hint) + '</p>' : '') +
            (withRetry ? '<button type="button" class="retry-btn" data-action="retry">Erneut versuchen</button>' : '') +
        '</div>';
    updateSelectionState();
}

function fetchAppointmentsAjax() {
    var startDate = $('#start_date').value;
    var endDate = $('#end_date').value;
    var calendarIds = [];
    $$('.calendar-checkbox:checked').forEach(function (cb) {
        calendarIds.push(cb.value);
    });

    if (calendarIds.length === 0) {
        fetchSequence++;
        showListMessage('Kein Kalender ausgewählt.', 'Wähle unter „Kalender“ mindestens einen aus.', false);
        return;
    }

    var sequence = ++fetchSequence;
    $('.appointments-main').innerHTML =
        '<div class="appointments-loading">' +
            '<span class="spinner-ring-inline spinner-ring-inline--dark"></span>' +
            '<span>Termine werden geladen…</span>' +
        '</div>';
    setExportSummary('Termine werden geladen…');

    var params = new URLSearchParams();
    params.append('start_date', startDate);
    params.append('end_date', endDate);
    calendarIds.forEach(function (id) {
        params.append('calendar_ids', id);
    });

    fetch('/api/appointments?' + params.toString())
        .then(function (res) {
            if (res.status === 401) {
                window.location.href = '/';
                return;
            }
            if (!res.ok) return responseError(res, 'Termine konnten nicht geladen werden').then(function (err) { throw err; });
            return res.json();
        })
        .then(function (data) {
            if (!data || sequence !== fetchSequence) return;
            renderAppointments(data.appointments);
        })
        .catch(function (err) {
            if (sequence !== fetchSequence) return;
            showListMessage('Termine konnten nicht geladen werden.', errorText(err), true);
        });
}

// --- Selection, export bar and preview ---

function checkedAppointmentIds() {
    var ids = [];
    $$('.appointment-checkbox:checked').forEach(function (cb) { ids.push(cb.value); });
    return ids;
}

function setExportSummary(text) {
    $('#export_summary').textContent = text;
}

function updateSelectionState() {
    var boxes = $$('.appointment-checkbox');
    var total = boxes.length;
    var checked = checkedAppointmentIds().length;

    boxes.forEach(function (cb) {
        cb.closest('.appointment-item').classList.toggle('is-deselected', !cb.checked);
    });

    var counter = $('.appointment-count');
    if (counter) counter.textContent = checked + ' von ' + total + ' ausgewählt';
    var selectAll = $('#select_all');
    if (selectAll) {
        selectAll.checked = total > 0 && checked === total;
        selectAll.indeterminate = checked > 0 && checked < total;
        selectAll.setAttribute('aria-label', checked === total ? 'Alle abwählen' : 'Alle auswählen');
    }

    $('#generate_pdf_btn').disabled = checked === 0;
    $('#generate_jpeg_btn').disabled = checked === 0;
    if (total === 0) {
        setExportSummary('Keine Termine zum Exportieren.');
    } else if (checked === 0) {
        setExportSummary('Wähle mindestens einen Termin aus.');
    } else {
        setExportSummary(checked === 1 ? '1 Termin wird exportiert' : checked + ' Termine werden exportiert');
    }

    updatePreview();
}

function hexToRgba(hex, alpha) {
    var value = parseInt(hex.slice(1), 16);
    return 'rgba(' + ((value >> 16) & 255) + ',' + ((value >> 8) & 255) + ',' + (value & 255) + ',' + (alpha / 255).toFixed(3) + ')';
}

// Mirrors _format_time_range in app/services/pdf/slides.py
function slideTimeText(app) {
    if (app.all_day) {
        var multiDay = app.end_date.slice(0, 10) !== app.start_date.slice(0, 10);
        return multiDay ? 'Ganztägig bis ' + formatShortDate(app.end_date) + app.end_date.slice(0, 4) : 'Ganztägig';
    }
    return app.start_time_view + ' - ' + app.end_time_view + ' Uhr';
}

function updatePreview() {
    var background = $('#background_color').value;
    var dateColor = $('#date_color').value;
    var textColor = $('#description_color').value;
    var alpha = parseInt($('#alpha').value, 10);

    $('#slide_box').style.backgroundColor = hexToRgba(background, alpha);
    $('#slide_date').style.color = dateColor;
    $('#slide_time').style.color = textColor;
    $('#slide_place').style.color = textColor;
    $('#slide_info').style.color = textColor;
    $('#swatch_background').style.background = background;
    $('#swatch_date').style.background = dateColor;
    $('#swatch_description').style.background = textColor;

    var ids = checkedAppointmentIds();
    var app = ids.length ? appointmentsById[ids[0]] : null;
    if (!app) return; // keep the sample content

    var textarea = $('textarea[name="additional_info_' + ids[0] + '"]');
    var customText = textarea ? textarea.value.trim() : '';
    $('#slide_date').textContent = formatDateWithWeekday(app.start_date_view);
    $('#slide_time').textContent = slideTimeText(app);
    $('#slide_place').textContent = app.meeting_at || '';
    $('#slide_title').textContent = app.title;
    $('#slide_info').textContent = customText || app.information || '';
}

function generateOutput(type) {
    var appointmentIds = checkedAppointmentIds();
    var errorEl = $('#generate_error');
    errorEl.hidden = true;
    if (appointmentIds.length === 0) return;

    var startDate = $('#start_date').value;
    var endDate = $('#end_date').value;
    var calendarIds = [];
    $$('.calendar-checkbox:checked').forEach(function (cb) {
        calendarIds.push(cb.value);
    });

    var additionalInfos = {};
    appointmentIds.forEach(function (id) {
        var textarea = $('textarea[name="additional_info_' + id + '"]');
        if (textarea) additionalInfos[id] = textarea.value;
    });

    var payload = {
        type: type,
        start_date: startDate,
        end_date: endDate,
        calendar_ids: calendarIds,
        appointment_ids: appointmentIds,
        color_settings: {
            background_color: $('#background_color').value,
            background_alpha: parseInt($('#alpha').value, 10),
            date_color: $('#date_color').value,
            description_color: $('#description_color').value
        },
        additional_infos: additionalInfos
    };

    var btn = type === 'pdf' ? $('#generate_pdf_btn') : $('#generate_jpeg_btn');
    showButtonSpinner(btn);

    csrfFetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(function (res) {
        if (res.status === 401) {
            window.location.href = '/';
            return;
        }
        if (!res.ok) {
            return responseError(res, 'Fehler beim Generieren').then(function (err) { throw err; });
        }
        var disposition = res.headers.get('Content-Disposition') || '';
        var filenameMatch = disposition.match(/filename=([^;]+)/);
        var filename = filenameMatch ? filenameMatch[1] : (type === 'pdf' ? 'appointments.pdf' : 'appointments.zip');
        var mimeType = type === 'pdf' ? 'application/pdf' : 'application/zip';
        return res.arrayBuffer().then(function (buf) {
            return { blob: new Blob([buf], { type: mimeType }), filename: filename };
        });
    })
    .then(function (result) {
        if (!result) return;
        var url = URL.createObjectURL(result.blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = result.filename;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        setTimeout(function () {
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 100);
        hideButtonSpinner(btn);
    })
    .catch(function (err) {
        console.error('Generate error:', err);
        errorEl.textContent = errorText(err) || 'Unbekannter Fehler';
        errorEl.hidden = false;
        hideButtonSpinner(btn);
    });
}

// --- Image uploads (background, logo) ---

function setupImageControls(kind, labels) {
    var uploadBtn = $('#' + kind + '_upload_btn');
    var input = $('#' + kind + '_upload');
    var deleteBtn = $('#' + kind + '_delete');
    var status = $('#' + kind + '_status');
    var images = [$(kind === 'bg' ? '#slide_bg' : '#slide_logo'), $('#' + kind + '_thumb')];
    var url = kind === 'bg' ? '/background' : '/logo';

    function showState(hasImage) {
        status.textContent = hasImage ? 'Hochgeladen' : labels.empty;
        $('.btn-label', uploadBtn).textContent = hasImage ? 'Ersetzen' : 'Hochladen';
        deleteBtn.hidden = !hasImage;
        var src = url + '?' + Date.now();
        images.forEach(function (img) {
            img.hidden = !hasImage;
            if (hasImage) img.src = src;
            else img.removeAttribute('src');
        });
    }

    uploadBtn.addEventListener('click', function () { input.click(); });

    input.addEventListener('change', function () {
        var file = this.files[0];
        if (!file) return;
        var formData = new FormData();
        formData.append('file', file);
        showButtonSpinner(uploadBtn);
        csrfFetch(url + '/upload', { method: 'POST', body: formData })
            .then(function (res) {
                if (!res.ok) return responseError(res, 'Upload fehlgeschlagen').then(function (err) { throw err; });
                return res.json();
            })
            .then(function () {
                hideButtonSpinner(uploadBtn);
                showState(true);
            })
            .catch(function (err) {
                hideButtonSpinner(uploadBtn);
                alert(errorText(err));
            });
        this.value = '';
    });

    deleteBtn.addEventListener('click', function () {
        csrfFetch(url, { method: 'DELETE' })
            .then(function (res) {
                if (!res.ok) return responseError(res, 'Löschen fehlgeschlagen').then(function (err) { throw err; });
                showState(false);
            })
            .catch(function (err) { alert(errorText(err)); });
    });
}

// flatpickr hides the labelled input and shows a generated one; give that one the label
function labelDateInputs() {
    [['_fpStart', 'Von'], ['_fpEnd', 'Bis']].forEach(function (entry) {
        var picker = window[entry[0]];
        if (picker && picker.altInput) picker.altInput.setAttribute('aria-label', entry[1]);
    });
}

// --- Initialization ---

document.addEventListener('DOMContentLoaded', function () {
    // Flatpickr — German locale, display dd.mm.yyyy, store yyyy-mm-dd in hidden fields.
    // Every date change reloads the list (debounced).
    window._fpStart = flatpickr('#start_date_display', {
        locale: 'de',
        dateFormat: 'Y-m-d',
        altInput: true,
        altFormat: 'd.m.Y',
        allowInput: true,
        onChange: function (selectedDates, dateStr) {
            $('#start_date').value = dateStr;
            scheduleFetch();
        }
    });

    window._fpEnd = flatpickr('#end_date_display', {
        locale: 'de',
        dateFormat: 'Y-m-d',
        altInput: true,
        altFormat: 'd.m.Y',
        allowInput: true,
        onChange: function (selectedDates, dateStr) {
            $('#end_date').value = dateStr;
            scheduleFetch();
        }
    });

    labelDateInputs();

    // Initialize from hidden ISO values
    var startIso = $('#start_date').value;
    var endIso = $('#end_date').value;
    if (startIso) window._fpStart.setDate(startIso, true);
    if (endIso) window._fpEnd.setDate(endIso, true);

    // Set defaults if no values provided
    if (!startIso || !endIso) {
        var thisWeek = calculateThisWeekDates();
        setDateRange(thisWeek.start, thisWeek.end);
        $('#start_date').value = formatIso(thisWeek.start);
        $('#end_date').value = formatIso(thisWeek.end);
    }

    // Date preset buttons (setDateRange triggers onChange, which reloads)
    $('#today').addEventListener('click', function () {
        var today = new Date();
        setDateRange(today, today);
    });

    $('#this-week').addEventListener('click', function () {
        var thisWeek = calculateThisWeekDates();
        setDateRange(thisWeek.start, thisWeek.end);
    });

    $('#next-week').addEventListener('click', function () {
        var nextWeek = calculateNextWeekDates();
        setDateRange(nextWeek.start, nextWeek.end);
    });

    // Generate buttons
    $('#generate_pdf_btn').addEventListener('click', function () { generateOutput('pdf'); });
    $('#generate_jpeg_btn').addEventListener('click', function () { generateOutput('jpeg'); });

    // Event delegation for dynamic content on appointments-main
    $('.appointments-main').addEventListener('click', function (e) {
        var target = e.target;

        if (target.closest('[data-action="retry"]')) {
            fetchAppointmentsAjax();
            return;
        }

        // Pencil button or custom text preview: edit the custom text
        var editTrigger = target.closest('[data-action="edit-custom-text"]');
        if (editTrigger) {
            e.preventDefault();
            var editItem = editTrigger.closest('.appointment-item');
            if (editItem.classList.contains('is-editing')) {
                closeCustomTextEditor(editItem);
            } else {
                openCustomTextEditor(editItem);
            }
            return;
        }

        // The time column selects like the title label does
        var timeColumn = target.closest('[data-action="toggle-select"]');
        if (timeColumn) {
            var checkbox = timeColumn.closest('.appointment-item').querySelector('.appointment-checkbox');
            checkbox.checked = !checkbox.checked;
            updateSelectionState();
            return;
        }

        // Expand/collapse info text
        var infoText = target.closest('[data-action="toggle-expand"]');
        if (infoText) {
            infoText.classList.toggle('expanded');
        }
    });

    // Event delegation for checkbox changes
    $('.appointments-main').addEventListener('change', function (e) {
        if (e.target.id === 'select_all') {
            var selectAll = e.target.checked;
            $$('.appointment-checkbox').forEach(function (cb) { cb.checked = selectAll; });
            updateSelectionState();
        } else if (e.target.classList.contains('appointment-checkbox')) {
            updateSelectionState();
        }
    });

    // Custom text editing: grow while typing, show the override state live, close on blur
    $('.appointments-main').addEventListener('input', function (e) {
        if (e.target.tagName === 'TEXTAREA') {
            autoResizeTextarea(e.target);
            var editItem = e.target.closest('.appointment-item');
            editItem.classList.toggle('has-custom-text', e.target.value.trim().length > 0);
            updatePreview();
        }
    });

    $('.appointments-main').addEventListener('focusout', function (e) {
        if (e.target.tagName !== 'TEXTAREA') return;
        var editItem = e.target.closest('.appointment-item');
        // Clicking the pencil again toggles itself; do not close twice
        if (e.relatedTarget && e.relatedTarget.closest('.appointment-item') === editItem &&
            e.relatedTarget.matches('[data-action="edit-custom-text"]')) return;
        closeCustomTextEditor(editItem);
    });

    $('.appointments-main').addEventListener('keydown', function (e) {
        if (e.target.tagName === 'TEXTAREA' && e.key === 'Escape') {
            e.target.blur();
        }
    });

    // Colors and opacity update the preview live
    ['#background_color', '#date_color', '#description_color'].forEach(function (selector) {
        $(selector).addEventListener('input', updatePreview);
    });
    $('#alpha').addEventListener('input', function () {
        $('#alphaValue').textContent = Math.round(this.value / 255 * 100) + '%';
        updatePreview();
    });

    // Calendar chips toggle (CSS collapse)
    $('#calendars_toggle').addEventListener('click', function () {
        var wrap = $('#calendars_wrap');
        var isExpanded = this.getAttribute('aria-expanded') === 'true';
        wrap.classList.toggle('is-open', !isExpanded);
        this.setAttribute('aria-expanded', isExpanded ? 'false' : 'true');
    });

    // Calendar selection: update the counter and reload
    document.addEventListener('change', function (e) {
        if (e.target.classList.contains('calendar-checkbox')) {
            var total = $$('.calendar-checkbox').length;
            var checked = $$('.calendar-checkbox:checked').length;
            var info = $('.calendar-selection-info');
            if (info) info.textContent = checked + ' von ' + total;
            scheduleFetch(700);
        }
    });

    setupImageControls('bg', { empty: 'Keins – weißer Hintergrund' });
    setupImageControls('logo', { empty: 'Keins' });

    updatePreview();

    // Initial load (replaces the loads scheduled by initializing the date pickers)
    scheduleFetch(0);
});
