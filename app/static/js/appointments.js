/* appointments.js — Vanilla JS (no jQuery) */

const $ = (s, c = document) => c.querySelector(s);
const $$ = (s, c = document) => c.querySelectorAll(s);

// --- CSRF token helper ---

function getCsrfToken() {
    var meta = $('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    var match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : '';
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
    textarea.style.height = '24px';
    if (textarea.value.trim().length > 0) {
        if (textarea.scrollHeight > 24) {
            textarea.style.height = textarea.scrollHeight + 'px';
        }
    }
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

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
        var hasInfo = app.additional_info && app.additional_info.trim().length > 0;
        var hasDescription = app.information && app.information.trim().length > 0;
        var delay = Math.min(itemIndex * 0.03, 0.6);
        html += '<div class="appointment-item" style="animation-delay:' + delay + 's">' +
            '<input type="checkbox" id="appointment-' + escapeHtml(app.id) + '" name="appointment_id"' +
            ' value="' + escapeHtml(app.id) + '" class="appointment-checkbox" checked>' +
            '<label for="appointment-' + escapeHtml(app.id) + '" class="appointment-label">' +
                '<span class="appointment-date">' +
                    (app.start_time_view === app.end_time_view
                        ? 'Ganztägig'
                        : escapeHtml(app.start_time_view) + ' – ' + escapeHtml(app.end_time_view)) +
                '</span>' +
                '<span class="appointment-description">' + escapeHtml(app.title) + '</span>' +
                '<button type="button" class="add-info-toggle' + (hasInfo ? ' hidden' : '') + '"' +
                    ' data-action="show-textarea">' +
                    '+ Eigener Text' +
                '</button>' +
            '</label>' +
            (hasDescription
                ? '<span class="appointment-info-text' + (hasInfo ? ' overridden' : '') + '" data-action="toggle-expand">' + escapeHtml(app.information) + '</span>'
                : '') +
            '<textarea name="additional_info_' + escapeHtml(app.id) + '"' +
                ' class="' + (hasInfo ? '' : 'hidden') + '"' +
                ' placeholder="Überschreibt die Beschreibung in der Ausgabe">' + escapeHtml(app.additional_info || '') + '</textarea>' +
            '</div>';
        itemIndex++;
    });

    html += '</div>';
    main.innerHTML = html;

    // Auto-resize existing textareas
    $$('textarea', main).forEach(function (textarea) {
        setTimeout(function () { autoResizeTextarea(textarea); }, 50);
    });

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

    fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify(payload)
    })
    .then(function (res) {
        if (res.status === 401) {
            window.location.href = '/';
            return;
        }
        if (!res.ok) {
            return res.json().then(function (data) {
                throw new Error(data.error || data.detail || 'Fehler beim Generieren');
            });
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
        errorEl.textContent = err.message || 'Unbekannter Fehler';
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

        // "+ Eigener Text" button
        var infoBtn = target.closest('[data-action="show-textarea"]');
        if (infoBtn) {
            e.preventDefault();
            infoBtn.classList.add('hidden');
            var ta = infoBtn.closest('.appointment-item').querySelector('textarea');
            if (ta) { ta.classList.remove('hidden'); ta.focus(); }
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

    // Event delegation for textarea input (auto-resize + overridden state)
    $('.appointments-main').addEventListener('input', function (e) {
        if (e.target.tagName === 'TEXTAREA') {
            autoResizeTextarea(e.target);
            var infoText = e.target.closest('.appointment-item').querySelector('.appointment-info-text');
            if (infoText) {
                infoText.classList.toggle('overridden', e.target.value.trim().length > 0);
            }
        }
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
        fetch('/logo/upload', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, body: formData })
            .then(function (res) {
                if (!res.ok) return res.text().then(function (t) { throw new Error('Upload fehlgeschlagen: ' + t); });
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
                alert(err.message);
                hideButtonSpinner(btn);
            });
        this.value = '';
    });

    // Logo delete
    $('#logo_delete').addEventListener('click', function () {
        fetch('/logo', { method: 'DELETE', headers: { 'X-CSRF-Token': getCsrfToken() } })
            .then(function (res) {
                if (!res.ok) return res.text().then(function (t) { throw new Error('Löschen fehlgeschlagen: ' + t); });
                $('#logo-preview').style.display = 'none';
                $('#logo_delete').style.display = 'none';
            })
            .catch(function (err) { alert(err.message); });
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
        fetch('/background/upload', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, body: formData })
            .then(function (res) {
                if (!res.ok) return res.text().then(function (t) { throw new Error('Upload fehlgeschlagen: ' + t); });
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
                alert(err.message);
                hideButtonSpinner(btn);
            });
        this.value = '';
    });

    // Background image delete
    $('#bg_delete').addEventListener('click', function () {
        fetch('/background', { method: 'DELETE', headers: { 'X-CSRF-Token': getCsrfToken() } })
            .then(function (res) {
                if (!res.ok) return res.text().then(function (t) { throw new Error('Löschen fehlgeschlagen: ' + t); });
                $('#bg-preview').style.display = 'none';
                $('#bg_delete').style.display = 'none';
            })
            .catch(function (err) { alert(err.message); });
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
