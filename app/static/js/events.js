/* events.js — Shared JS for Agenda and Services pages */

var $ = function (s, c) { return (c || document).querySelector(s); };
var $$ = function (s, c) { return (c || document).querySelectorAll(s); };

// --- CSRF token helper ---

function getCsrfToken() {
    var meta = $('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    var match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : '';
}

// --- Page mode detection ---

function getPageMode() {
    var meta = $('meta[name="page-mode"]');
    return meta ? meta.getAttribute('content') : 'agenda';
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

function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatIso(date) {
    var y = date.getFullYear();
    var m = String(date.getMonth() + 1).padStart(2, '0');
    var d = String(date.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + d;
}

function formatDateTime(isoStr) {
    if (!isoStr) return '';
    var d = new Date(isoStr);
    var day = String(d.getDate()).padStart(2, '0');
    var month = String(d.getMonth() + 1).padStart(2, '0');
    var year = d.getFullYear();
    var hours = String(d.getHours()).padStart(2, '0');
    var mins = String(d.getMinutes()).padStart(2, '0');
    return day + '.' + month + '.' + year + ' ' + hours + ':' + mins;
}

function formatDateShort(isoStr) {
    if (!isoStr) return '';
    var d = new Date(isoStr);
    var days = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
    var day = String(d.getDate()).padStart(2, '0');
    var month = String(d.getMonth() + 1).padStart(2, '0');
    var hours = String(d.getHours()).padStart(2, '0');
    var mins = String(d.getMinutes()).padStart(2, '0');
    return days[d.getDay()] + ' ' + day + '.' + month + '. ' + hours + ':' + mins;
}

// --- Flatpickr helpers ---

function setDateRange(startDate, endDate) {
    if (window._fpStart) window._fpStart.setDate(startDate, true);
    if (window._fpEnd) window._fpEnd.setDate(endDate, true);
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

// --- Build query params ---

function buildEventParams() {
    var startDate = $('#start_date').value;
    var endDate = $('#end_date').value;
    var calendarIds = [];
    // For checkboxes, only include checked ones; for hidden inputs, include all
    $$('.calendar-checkbox').forEach(function (cb) {
        if (cb.type === 'hidden' || cb.checked) {
            calendarIds.push(cb.value);
        }
    });

    var params = new URLSearchParams();
    params.append('start_date', startDate);
    params.append('end_date', endDate);
    calendarIds.forEach(function (id) {
        params.append('calendar_ids', id);
    });
    return params;
}

// --- Agenda rendering ---

function renderAgendaEvents(events) {
    var container = $('#events-list');

    if (!events || events.length === 0) {
        container.innerHTML =
            '<div class="empty-state">' +
                '<p>Keine Events gefunden.</p>' +
                '<p class="empty-state-hint">Bitte Datum und Kalender anpassen.</p>' +
            '</div>';
        return;
    }

    var html = '<div class="events-count">' + events.length + ' Event' + (events.length !== 1 ? 's' : '') + ' gefunden</div>';

    events.forEach(function (ev, i) {
        var delay = Math.min(i * 0.04, 0.8);
        html += '<div class="event-card" data-event-id="' + ev.id + '" style="animation-delay:' + delay + 's">' +
            '<div class="event-card-header">' +
                '<svg class="event-expand-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>' +
                '<div class="event-card-info">' +
                    '<div class="event-card-title">' + escapeHtml(ev.name) + '</div>' +
                    '<div class="event-card-meta">' + escapeHtml(formatDateShort(ev.start_date)) + '</div>' +
                '</div>' +
                '<span class="event-card-calendar">' + escapeHtml(ev.calendar_name) + '</span>' +
            '</div>' +
            '<div class="event-card-body">' +
                '<div class="agenda-loading">' +
                    '<span class="spinner-ring-inline spinner-ring-inline--dark"></span>' +
                    '<span>Agenda wird geladen&hellip;</span>' +
                '</div>' +
            '</div>' +
        '</div>';
    });

    container.innerHTML = html;
}

function toggleEventCard(card) {
    var isExpanded = card.classList.contains('is-expanded');

    if (isExpanded) {
        card.classList.remove('is-expanded');
        return;
    }

    card.classList.add('is-expanded');

    // Only fetch if not already loaded
    var body = $('.event-card-body', card);
    if (body.dataset.loaded === 'true') return;

    var eventId = card.dataset.eventId;
    fetchAgenda(eventId, body);
}

function fetchAgenda(eventId, bodyEl) {
    fetch('/api/events/' + eventId + '/agenda')
        .then(function (res) {
            if (res.status === 401) {
                window.location.href = '/';
                return;
            }
            if (!res.ok) throw new Error('Fehler beim Laden der Agenda');
            return res.json();
        })
        .then(function (data) {
            if (!data) return;
            bodyEl.dataset.loaded = 'true';
            renderAgendaTable(data.items, bodyEl, eventId);
        })
        .catch(function (err) {
            bodyEl.innerHTML = '<div class="empty-state"><p>' + escapeHtml(err.message) + '</p></div>';
        });
}

function renderAgendaTable(items, bodyEl, eventId) {
    if (!items || items.length === 0) {
        bodyEl.innerHTML = '<div class="empty-state"><p>Keine Agenda vorhanden.</p></div>';
        return;
    }

    // Separate before-event items
    var beforeItems = [];
    var mainItems = [];
    items.forEach(function (item) {
        if (item.is_before_event) {
            beforeItems.push(item);
        } else {
            mainItems.push(item);
        }
    });

    var html = '<table class="agenda-table">' +
        '<thead><tr>' +
            '<th>Zeit</th>' +
            '<th>Titel</th>' +
            '<th>Dauer</th>' +
            '<th>Verantwortlich</th>' +
            '<th>Notiz</th>' +
        '</tr></thead><tbody>';

    // Before-event section
    if (beforeItems.length > 0) {
        html += '<tr class="agenda-header-row"><td colspan="5">Vor dem Gottesdienst</td></tr>';
        beforeItems.forEach(function (item) {
            html += renderAgendaRow(item, true);
        });
        html += '<tr class="agenda-header-row"><td colspan="5">Gottesdienst</td></tr>';
    }

    // Main items
    mainItems.forEach(function (item) {
        if (item.type === 'header') {
            html += '<tr class="agenda-header-row"><td colspan="5">' + escapeHtml(item.title) + '</td></tr>';
        } else {
            html += renderAgendaRow(item, false);
        }
    });

    html += '</tbody></table>';

    bodyEl.innerHTML = html;
}

function renderAgendaRow(item, isBefore) {
    var rowClass = isBefore ? ' class="agenda-before-event"' : '';
    var titleHtml = escapeHtml(item.title);

    // Song info
    if (item.type === 'song' && (item.song_key || item.song_arrangement)) {
        var parts = [];
        if (item.song_key) parts.push(escapeHtml(item.song_key));
        if (item.song_arrangement) parts.push(escapeHtml(item.song_arrangement));
        titleHtml += '<br><span class="agenda-song-info">' + parts.join(' / ') + '</span>';
    }

    // Note
    var noteHtml = '';
    if (item.note) {
        noteHtml = '<span class="agenda-note">' + escapeHtml(item.note) + '</span>';
    }

    // Responsible persons
    var responsible = '';
    if (item.responsible_names && item.responsible_names.length > 0) {
        responsible = escapeHtml(item.responsible_names.join(', '));
    }

    return '<tr' + rowClass + '>' +
        '<td>' + escapeHtml(item.start || '') + '</td>' +
        '<td>' + titleHtml + '</td>' +
        '<td>' + escapeHtml(item.duration_display || '') + '</td>' +
        '<td>' + responsible + '</td>' +
        '<td>' + noteHtml + '</td>' +
    '</tr>';
}

// --- Services rendering ---

function renderServicesTable(events) {
    var container = $('#events-list');

    if (!events || events.length === 0) {
        container.innerHTML =
            '<div class="empty-state">' +
                '<p>Keine Events gefunden.</p>' +
                '<p class="empty-state-hint">Bitte Datum und Kalender anpassen.</p>' +
            '</div>';
        return;
    }

    var html = '<div class="events-count">' + events.length + ' Event' + (events.length !== 1 ? 's' : '') + ' gefunden</div>';

    html += '<div class="services-table-wrapper">' +
        '<table class="services-table">' +
        '<thead><tr>' +
            '<th>Event</th>' +
            '<th>Dienst</th>' +
            '<th>Person</th>' +
            '<th>Status</th>' +
        '</tr></thead><tbody>';

    events.forEach(function (ev) {
        var serviceCount = ev.services ? ev.services.length : 0;

        // Event group header
        html += '<tr class="services-event-header">' +
            '<td colspan="4">' +
                escapeHtml(ev.name) +
                '<span class="services-event-meta">' + escapeHtml(formatDateShort(ev.start_date)) + ' &mdash; ' + escapeHtml(ev.calendar_name) + '</span>' +
            '</td>' +
        '</tr>';

        if (serviceCount === 0) {
            html += '<tr><td colspan="4" class="status-open">Keine Dienste zugewiesen</td></tr>';
        } else {
            ev.services.forEach(function (svc) {
                var personHtml = svc.person_name
                    ? escapeHtml(svc.person_name)
                    : '<span class="status-open">&mdash; (offen)</span>';

                var statusHtml = '';
                if (!svc.person_name) {
                    statusHtml = '<span class="status-open">?</span>';
                } else if (svc.is_accepted) {
                    statusHtml = '<span class="status-accepted">&#10003; Zugesagt</span>';
                } else {
                    statusHtml = '<span class="status-pending">? Ausstehend</span>';
                }

                html += '<tr>' +
                    '<td></td>' +
                    '<td>' + escapeHtml(svc.name) + '</td>' +
                    '<td>' + personHtml + '</td>' +
                    '<td>' + statusHtml + '</td>' +
                '</tr>';
            });
        }
    });

    html += '</tbody></table></div>';

    container.innerHTML = html;
}

// --- Load events (shared) ---

function loadEvents() {
    var fetchBtn = $('#fetch_btn');
    showButtonSpinner(fetchBtn);

    var container = $('#events-list');
    container.innerHTML =
        '<div class="events-loading">' +
            '<span class="spinner-ring-inline spinner-ring-inline--dark"></span>' +
            '<span>Events werden geladen&hellip;</span>' +
        '</div>';

    var params = buildEventParams();

    fetch('/api/events?' + params.toString())
        .then(function (res) {
            if (res.status === 401) {
                window.location.href = '/';
                return;
            }
            if (!res.ok) throw new Error('Fehler beim Laden der Events');
            return res.json();
        })
        .then(function (data) {
            if (!data) return;
            var mode = getPageMode();
            if (mode === 'services') {
                renderServicesTable(data.events);
            } else {
                renderAgendaEvents(data.events);
            }
            hideButtonSpinner(fetchBtn);
        })
        .catch(function (err) {
            container.innerHTML =
                '<div class="empty-state">' +
                    '<p>' + escapeHtml(err.message) + '</p>' +
                '</div>';
            hideButtonSpinner(fetchBtn);
        });
}

// --- Initialization ---

document.addEventListener('DOMContentLoaded', function () {
    // Flatpickr
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

    // Set defaults if no values
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
        loadEvents();
    });

    $('#this-week').addEventListener('click', function () {
        var thisWeek = calculateThisWeekDates();
        setDateRange(thisWeek.start, thisWeek.end);
        $('#start_date').value = formatIso(thisWeek.start);
        $('#end_date').value = formatIso(thisWeek.end);
        loadEvents();
    });

    $('#next-week').addEventListener('click', function () {
        var nextWeek = calculateNextWeekDates();
        setDateRange(nextWeek.start, nextWeek.end);
        $('#start_date').value = formatIso(nextWeek.start);
        $('#end_date').value = formatIso(nextWeek.end);
        loadEvents();
    });

    // Fetch button
    $('#fetch_btn').addEventListener('click', loadEvents);

    // Calendar chips toggle (only on pages with calendar selection)
    var calToggle = $('#calendars_toggle');
    if (calToggle) {
        calToggle.addEventListener('click', function () {
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
    }

    // Calendar chip counter
    document.addEventListener('change', function (e) {
        if (e.target.classList.contains('calendar-checkbox')) {
            var total = $$('.calendar-checkbox').length;
            var checked = $$('.calendar-checkbox:checked').length;
            var info = $('.calendar-selection-info');
            if (info) info.textContent = checked + ' von ' + total;
        }
    });

    // Event delegation for agenda card expand/collapse
    var eventsContainer = $('#events-list');
    eventsContainer.addEventListener('click', function (e) {
        var header = e.target.closest('.event-card-header');
        if (header) {
            var card = header.closest('.event-card');
            if (card) toggleEventCard(card);
        }
    });

    // Auto-fetch on page load
    loadEvents();
});
