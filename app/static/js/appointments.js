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

function renderAppointments(appointments) {
    var main = $('.appointments-main');

    if (!appointments || appointments.length === 0) {
        main.innerHTML =
            '<div class="empty-state">' +
                '<p>Keine Termine vorhanden.</p>' +
                '<p class="empty-state-hint">Bitte Datum und Kalender auswählen und "Termine laden" klicken.</p>' +
            '</div>';
        checkAppointments();
        return;
    }

    var html = '<div class="appointments-actions">' +
        '<span class="appointment-count">' + appointments.length + ' von ' + appointments.length + ' ausgewählt</span>' +
        '<button type="button" id="selectAllAppointments" class="select-all-btn">Alle auswählen</button>' +
        '<button type="button" id="deselectAllAppointments" class="deselect-all-btn">Alle abwählen</button>' +
        '</div>' +
        '<div class="appointments-container">';

    var lastDate = null;
    var itemIndex = 0;
    appointments.forEach(function (app) {
        var dateKey = app.start_date_view;
        if (dateKey !== lastDate) {
            html += '<div class="date-group-header">' + escapeHtml(formatDateWithWeekday(dateKey)) + '</div>';
            lastDate = dateKey;
        }
        var customText = (app.additional_info || '').trim();
        var hasDescription = app.information && app.information.trim().length > 0;
        var delay = Math.min(itemIndex * 0.03, 0.6);
        var checkboxId = 'appointment-' + escapeHtml(app.id);
        html += '<div class="appointment-item' + (customText ? ' has-custom-text' : '') + '" style="animation-delay:' + delay + 's">' +
            '<input type="checkbox" id="' + checkboxId + '" name="appointment_id"' +
                ' value="' + escapeHtml(app.id) + '" class="appointment-checkbox" checked>' +
            '<label for="' + checkboxId + '" class="appointment-time">' + renderTimeColumn(app) + '</label>' +
            '<div class="appointment-body">' +
                '<label for="' + checkboxId + '" class="appointment-title">' + escapeHtml(app.title) + '</label>' +
                (hasDescription
                    ? '<p class="appointment-info-text" data-action="toggle-expand" title="Klicken zum Auf-/Zuklappen">' +
                        escapeHtml(app.information) + '</p>'
                    : '') +
                '<p class="appointment-custom-text" data-action="edit-custom-text" title="Eigenen Text bearbeiten">' +
                    escapeHtml(customText) + '</p>' +
                '<textarea name="additional_info_' + escapeHtml(app.id) + '" class="hidden" rows="2"' +
                    ' placeholder="Eigener Text – ersetzt die Beschreibung auf der Folie">' + escapeHtml(customText) + '</textarea>' +
            '</div>' +
            '<button type="button" class="custom-text-btn" data-action="edit-custom-text"' +
                ' aria-label="Eigenen Text bearbeiten" title="Eigener Text">' + PENCIL_ICON + '</button>' +
            '</div>';
        itemIndex++;
    });

    html += '</div>';
    main.innerHTML = html;

    checkAppointments();
}

function fetchAppointmentsAjax() {
    var startDate = $('#start_date').value;
    var endDate = $('#end_date').value;
    var calendarIds = [];
    $$('.calendar-checkbox:checked').forEach(function (cb) {
        calendarIds.push(cb.value);
    });

    var fetchBtn = $('#fetch_btn');
    showButtonSpinner(fetchBtn);
    $('.appointments-main').innerHTML =
        '<div class="appointments-loading">' +
            '<span class="spinner-ring-inline spinner-ring-inline--dark"></span>' +
            '<span>Termine werden geladen…</span>' +
        '</div>';

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
            if (!res.ok) throw new Error('Fehler beim Laden der Termine');
            return res.json();
        })
        .then(function (data) {
            if (!data) return;
            renderAppointments(data.appointments);
            hideButtonSpinner(fetchBtn);
        })
        .catch(function (err) {
            $('.appointments-main').innerHTML =
                '<div class="empty-state">' +
                    '<p>' + escapeHtml(err.message) + '</p>' +
                '</div>';
            hideButtonSpinner(fetchBtn);
        });
}

function updateSelectionCount() {
    var total = $$('.appointment-checkbox').length;
    var checked = $$('.appointment-checkbox:checked').length;
    var counter = $('.appointment-count');
    if (counter) counter.textContent = checked + ' von ' + total + ' ausgewählt';
    $$('.appointment-checkbox').forEach(function (cb) {
        cb.closest('.appointment-item').classList.toggle('is-deselected', !cb.checked);
    });
}

function checkAppointments() {
    var hasAppointments = $$('.appointment-checkbox').length > 0;

    $('#generate_pdf_btn').disabled = !hasAppointments;
    $('#generate_jpeg_btn').disabled = !hasAppointments;

    var errorEl = $('#generate_error');
    errorEl.style.display = hasAppointments ? 'none' : '';
}

function generateOutput(type) {
    var appointmentIds = [];
    $$('.appointment-checkbox:checked').forEach(function (cb) {
        appointmentIds.push(cb.value);
    });

    var errorEl = $('#generate_error');
    if (appointmentIds.length === 0) {
        errorEl.textContent = 'Bitte mindestens einen Termin auswählen.';
        errorEl.style.display = '';
        return;
    }
    errorEl.style.display = 'none';

    var additionalInfos = {};
    appointmentIds.forEach(function (id) {
        var textarea = $('textarea[name="additional_info_' + id + '"]');
        if (textarea && textarea.value.trim()) {
            additionalInfos[id] = textarea.value;
        }
    });

    var calendarIds = [];
    $$('.calendar-checkbox:checked').forEach(function (cb) {
        calendarIds.push(cb.value);
    });

    var payload = {
        type: type,
        start_date: $('#start_date').value,
        end_date: $('#end_date').value,
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
        var errorEl = $('#generate_error');
        errorEl.textContent = errorText(err) || 'Unbekannter Fehler';
        errorEl.style.display = '';
        hideButtonSpinner(btn);
    });
}

// --- Initialization ---

document.addEventListener('DOMContentLoaded', function () {
    // Flatpickr — German locale, display dd.mm.yyyy, store yyyy-mm-dd in hidden fields
    window._fpStart = flatpickr('#start_date_display', {
        locale: 'de',
        dateFormat: 'Y-m-d',
        altInput: true,
        altFormat: 'd.m.Y',
        allowInput: true,
        onChange: function (selectedDates, dateStr) {
            $('#start_date').value = dateStr;
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
        }
    });

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

    // Date preset buttons
    $('#today').addEventListener('click', function () {
        var today = new Date();
        setDateRange(today, today);
        $('#start_date').value = formatIso(today);
        $('#end_date').value = formatIso(today);
        fetchAppointmentsAjax();
    });

    $('#this-week').addEventListener('click', function () {
        var thisWeek = calculateThisWeekDates();
        setDateRange(thisWeek.start, thisWeek.end);
        $('#start_date').value = formatIso(thisWeek.start);
        $('#end_date').value = formatIso(thisWeek.end);
        fetchAppointmentsAjax();
    });

    $('#next-week').addEventListener('click', function () {
        var nextWeek = calculateNextWeekDates();
        setDateRange(nextWeek.start, nextWeek.end);
        $('#start_date').value = formatIso(nextWeek.start);
        $('#end_date').value = formatIso(nextWeek.end);
        fetchAppointmentsAjax();
    });

    // Fetch button
    $('#fetch_btn').addEventListener('click', fetchAppointmentsAjax);

    // Generate buttons
    $('#generate_pdf_btn').addEventListener('click', function () { generateOutput('pdf'); });
    $('#generate_jpeg_btn').addEventListener('click', function () { generateOutput('jpeg'); });

    // Event delegation for dynamic content on appointments-main
    $('.appointments-main').addEventListener('click', function (e) {
        // Select all / deselect all
        var target = e.target;
        if (target.id === 'selectAllAppointments' || target.closest('#selectAllAppointments')) {
            $$('.appointment-checkbox').forEach(function (cb) { cb.checked = true; });
            updateSelectionCount();
            return;
        }
        if (target.id === 'deselectAllAppointments' || target.closest('#deselectAllAppointments')) {
            $$('.appointment-checkbox').forEach(function (cb) { cb.checked = false; });
            updateSelectionCount();
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

        // Expand/collapse info text
        var infoText = target.closest('[data-action="toggle-expand"]');
        if (infoText) {
            infoText.classList.toggle('expanded');
        }
    });

    // Event delegation for checkbox changes
    $('.appointments-main').addEventListener('change', function (e) {
        if (e.target.classList.contains('appointment-checkbox')) {
            updateSelectionCount();
        }
    });

    // Custom text editing: grow while typing, show the override state live, close on blur
    $('.appointments-main').addEventListener('input', function (e) {
        if (e.target.tagName === 'TEXTAREA') {
            autoResizeTextarea(e.target);
            var editItem = e.target.closest('.appointment-item');
            editItem.classList.toggle('has-custom-text', e.target.value.trim().length > 0);
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

    // Transparency slider: show the value as percent
    $('#alpha').addEventListener('input', function () {
        $('#alphaValue').textContent = Math.round(this.value / 255 * 100) + '%';
    });

    // Calendar chips toggle (CSS collapse)
    $('#calendars_toggle').addEventListener('click', function () {
        var wrap = $('#calendars_wrap');
        var isExpanded = this.getAttribute('aria-expanded') === 'true';
        if (isExpanded) {
            wrap.classList.remove('is-open');
            this.setAttribute('aria-expanded', 'false');
        } else {
            wrap.classList.add('is-open');
            this.setAttribute('aria-expanded', 'true');
        }
    });

    // Calendar chip counter (delegated)
    document.addEventListener('change', function (e) {
        if (e.target.classList.contains('calendar-checkbox')) {
            var total = $$('.calendar-checkbox').length;
            var checked = $$('.calendar-checkbox:checked').length;
            var info = $('.calendar-selection-info');
            if (info) info.textContent = checked + ' von ' + total;
        }
    });

    // Logo upload
    $('#logo_upload_btn').addEventListener('click', function () {
        $('#logo_upload').click();
    });

    $('#logo_upload').addEventListener('change', function () {
        var file = this.files[0];
        if (!file) return;
        var formData = new FormData();
        formData.append('file', file);
        var btn = $('#logo_upload_btn');
        showButtonSpinner(btn);
        csrfFetch('/logo/upload', { method: 'POST', body: formData })
            .then(function (res) {
                if (!res.ok) return responseError(res, 'Upload fehlgeschlagen').then(function (err) { throw err; });
                return res.json();
            })
            .then(function () {
                $('#logo-img').src = '/logo?' + Date.now();
                $('#logo-preview').style.display = '';
                $('#logo_delete').style.display = '';
                hideButtonSpinner(btn);
                var label = $('.btn-label', btn);
                label.textContent = 'Gespeichert!';
                setTimeout(function () { label.textContent = 'Hochladen'; }, 2000);
            })
            .catch(function (err) {
                alert(errorText(err));
                hideButtonSpinner(btn);
            });
        this.value = '';
    });

    // Logo delete
    $('#logo_delete').addEventListener('click', function () {
        csrfFetch('/logo', { method: 'DELETE' })
            .then(function (res) {
                if (!res.ok) return responseError(res, 'Löschen fehlgeschlagen').then(function (err) { throw err; });
                $('#logo-preview').style.display = 'none';
                $('#logo_delete').style.display = 'none';
            })
            .catch(function (err) { alert(errorText(err)); });
    });

    // Background image upload
    $('#bg_upload_btn').addEventListener('click', function () {
        $('#bg_upload').click();
    });

    $('#bg_upload').addEventListener('change', function () {
        var file = this.files[0];
        if (!file) return;
        var formData = new FormData();
        formData.append('file', file);
        var btn = $('#bg_upload_btn');
        showButtonSpinner(btn);
        csrfFetch('/background/upload', { method: 'POST', body: formData })
            .then(function (res) {
                if (!res.ok) return responseError(res, 'Upload fehlgeschlagen').then(function (err) { throw err; });
                return res.json();
            })
            .then(function () {
                $('#bg-img').src = '/background?' + Date.now();
                $('#bg-preview').style.display = '';
                $('#bg_delete').style.display = '';
                hideButtonSpinner(btn);
                var label = $('.btn-label', btn);
                label.textContent = 'Gespeichert!';
                setTimeout(function () { label.textContent = 'Hochladen'; }, 2000);
            })
            .catch(function (err) {
                alert(errorText(err));
                hideButtonSpinner(btn);
            });
        this.value = '';
    });

    // Background image delete
    $('#bg_delete').addEventListener('click', function () {
        csrfFetch('/background', { method: 'DELETE' })
            .then(function (res) {
                if (!res.ok) return responseError(res, 'Löschen fehlgeschlagen').then(function (err) { throw err; });
                $('#bg-preview').style.display = 'none';
                $('#bg_delete').style.display = 'none';
            })
            .catch(function (err) { alert(errorText(err)); });
    });

    // Color presets
    var applyButton = document.getElementById('applyPreset');
    var colorPresetsSelect = document.getElementById('color_presets');

    var presets = {
        'preset1': {
            'date_color': '#c1540c',
            'description_color': '#4e4e4e',
            'background_color': '#ffffff',
            'background_alpha': 128
        }
    };

    if (applyButton) {
        applyButton.addEventListener('click', function () {
            var selectedPreset = colorPresetsSelect.value;
            if (presets[selectedPreset]) {
                document.getElementById('date_color').value = presets[selectedPreset].date_color;
                document.getElementById('description_color').value = presets[selectedPreset].description_color;
                document.getElementById('background_color').value = presets[selectedPreset].background_color;
                document.getElementById('alpha').value = presets[selectedPreset].background_alpha;
                document.getElementById('alphaValue').textContent = Math.round(presets[selectedPreset].background_alpha / 255 * 100) + '%';
            }
        });
    }

    // Initial button state
    checkAppointments();

    // Auto-fetch appointments on page load
    fetchAppointmentsAjax();
});
