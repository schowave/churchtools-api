/* events.js — Shared JS for Agenda and Services pages */

var $ = function (s, c) { return (c || document).querySelector(s); };
var $$ = function (s, c) { return (c || document).querySelectorAll(s); };

// --- Page mode detection ---

function getPageMode() {
    var meta = $('meta[name="page-mode"]');
    return meta ? meta.getAttribute('content') : 'agenda';
}

// --- Utility functions ---

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatIso(date) {
    var y = date.getFullYear();
    var m = String(date.getMonth() + 1).padStart(2, '0');
    var d = String(date.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + d;
}

function formatTime(isoStr) {
    if (!isoStr) return '';
    var d = new Date(isoStr);
    return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
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
    $$('.calendar-checkbox:checked').forEach(function (cb) {
        calendarIds.push(cb.value);
    });

    var params = new URLSearchParams();
    params.append('start_date', startDate);
    params.append('end_date', endDate);
    calendarIds.forEach(function (id) {
        params.append('calendar_ids', id);
    });
    return params;
}

// --- Shared rendering helpers ---

var CHEVRON_ICON = '<svg class="event-expand-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
    ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>';
var PDF_ICON = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>' +
    '<polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><polyline points="9 15 12 18 15 15"/></svg>';

function plural(count, one, many) {
    return count + ' ' + (count === 1 ? one : many);
}

function showListMessage(title, hint, withRetry) {
    $('#events-list').innerHTML =
        '<div class="empty-state">' +
            '<p>' + escapeHtml(title) + '</p>' +
            (hint ? '<p class="empty-state-hint">' + escapeHtml(hint) + '</p>' : '') +
            (withRetry ? '<button type="button" class="retry-btn" data-action="retry">Erneut versuchen</button>' : '') +
        '</div>';
}

function showNoEvents() {
    showListMessage('Keine Termine in diesem Zeitraum.', 'Wähle einen anderen Zeitraum oder weitere Kalender.', false);
}

function pdfLink(href, eventName) {
    return '<a href="' + href + '" class="btn-export" download aria-label="PDF für ' + escapeHtml(eventName) + ' herunterladen">' +
        PDF_ICON + '<span>PDF</span></a>';
}

// --- Agenda rendering ---

function renderAgendaEvents(events) {
    if (!events || events.length === 0) {
        showNoEvents();
        return;
    }

    var html = '<p class="events-count">' + plural(events.length, 'Termin', 'Termine') +
        ' <span class="events-count-hint">· zum Anzeigen der Agenda aufklappen</span></p>';

    events.forEach(function (ev, i) {
        var delay = Math.min(i * 0.04, 0.8);
        var bodyId = 'agenda-body-' + ev.id;
        html += '<div class="event-card" data-event-id="' + ev.id + '" style="animation-delay:' + delay + 's">' +
            '<button type="button" class="event-card-header" aria-expanded="false" aria-controls="' + bodyId + '">' +
                CHEVRON_ICON +
                '<span class="event-card-info">' +
                    '<span class="event-card-title">' + escapeHtml(ev.name) + '</span>' +
                    '<span class="event-card-meta">' + escapeHtml(formatDateShort(ev.start_date)) + '</span>' +
                '</span>' +
                '<span class="event-card-calendar">' + escapeHtml(ev.calendar_name) + '</span>' +
            '</button>' +
            '<div class="event-card-body" id="' + bodyId + '">' +
                '<div class="agenda-loading">' +
                    '<span class="spinner-ring-inline spinner-ring-inline--dark"></span>' +
                    '<span>Agenda wird geladen&hellip;</span>' +
                '</div>' +
            '</div>' +
        '</div>';
    });

    $('#events-list').innerHTML = html;
}

function toggleEventCard(card) {
    var header = $('.event-card-header', card);
    var isExpanded = card.classList.toggle('is-expanded');
    header.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
    if (!isExpanded) return;

    // Only fetch if not already loaded
    var body = $('.event-card-body', card);
    if (body.dataset.loaded === 'true') return;
    fetchAgenda(card.dataset.eventId, body, $('.event-card-title', card).textContent);
}

function fetchAgenda(eventId, bodyEl, eventName) {
    fetch('/api/events/' + eventId + '/agenda')
        .then(function (res) {
            if (res.status === 401) {
                window.location.href = '/';
                return;
            }
            if (!res.ok) throw new Error('Die Agenda konnte nicht geladen werden.');
            return res.json();
        })
        .then(function (data) {
            if (!data) return;
            bodyEl.dataset.loaded = 'true';
            renderAgendaTable(data.items, bodyEl, eventId, eventName);
        })
        .catch(function (err) {
            bodyEl.innerHTML = '<div class="agenda-empty">' + escapeHtml(err.message) + '</div>';
        });
}

function renderAgendaTable(items, bodyEl, eventId, eventName) {
    if (!items || items.length === 0) {
        bodyEl.innerHTML = '<div class="agenda-empty">Für diesen Termin gibt es in ChurchTools keine Agenda.</div>';
        return;
    }

    var beforeItems = items.filter(function (item) { return item.is_before_event; });
    var mainItems = items.filter(function (item) { return !item.is_before_event; });

    var html = '<div class="agenda-toolbar">' + pdfLink('/api/events/' + eventId + '/agenda/pdf', eventName) + '</div>' +
        '<table class="agenda-table">' +
        '<thead><tr>' +
            '<th scope="col">Zeit</th>' +
            '<th scope="col">Programmpunkt</th>' +
            '<th scope="col">Dauer</th>' +
            '<th scope="col">Verantwortlich</th>' +
            '<th scope="col">Notiz</th>' +
        '</tr></thead><tbody>';

    // "Vor dem Gottesdienst" / "Gottesdienst" are levels above the headers from ChurchTools
    if (beforeItems.length > 0) {
        html += '<tr class="agenda-part-row"><th colspan="5" scope="colgroup">Vor dem Gottesdienst</th></tr>';
        beforeItems.forEach(function (item) { html += renderAgendaItem(item, true); });
        html += '<tr class="agenda-part-row"><th colspan="5" scope="colgroup">Gottesdienst</th></tr>';
    }
    mainItems.forEach(function (item) { html += renderAgendaItem(item, false); });

    html += '</tbody></table>';
    bodyEl.innerHTML = html;
}

function renderAgendaItem(item, isBefore) {
    if (item.type === 'header') {
        return '<tr class="agenda-header-row"><td colspan="5">' + escapeHtml(item.title) + '</td></tr>';
    }

    var titleHtml = escapeHtml(item.title);
    if (item.type === 'song' && (item.song_key || item.song_arrangement)) {
        var parts = [];
        if (item.song_key) parts.push('Tonart ' + escapeHtml(item.song_key));
        if (item.song_arrangement) parts.push(escapeHtml(item.song_arrangement));
        titleHtml += '<span class="agenda-song-info">' + parts.join(' · ') + '</span>';
    }

    var responsible = item.responsible_names && item.responsible_names.length > 0
        ? escapeHtml(item.responsible_names.join(', '))
        : '';

    return '<tr' + (isBefore ? ' class="agenda-before-event"' : '') + '>' +
        '<td class="agenda-time">' + escapeHtml(formatTime(item.start)) + '</td>' +
        '<td class="agenda-title">' + titleHtml + '</td>' +
        '<td class="agenda-duration">' + escapeHtml(item.duration_display || '') + '</td>' +
        '<td class="agenda-responsible">' + responsible + '</td>' +
        '<td>' + (item.note ? '<span class="agenda-note">' + escapeHtml(item.note) + '</span>' : '') + '</td>' +
    '</tr>';
}

// --- Services rendering ---

function serviceStats(services) {
    var stats = { total: services.length, accepted: 0, pending: 0, open: 0 };
    services.forEach(function (svc) {
        if (!svc.person_name) stats.open++;
        else if (svc.is_accepted) stats.accepted++;
        else stats.pending++;
    });
    return stats;
}

function renderServiceStatus(svc) {
    if (!svc.person_name) return '<span class="status-badge status-open">Offen</span>';
    if (svc.is_accepted) return '<span class="status-badge status-accepted">Zugesagt</span>';
    return '<span class="status-badge status-pending">Ausstehend</span>';
}

function renderServicesTable(events) {
    if (!events || events.length === 0) {
        showNoEvents();
        return;
    }

    var openTotal = 0;
    events.forEach(function (ev) { openTotal += serviceStats(ev.services || []).open; });

    var html = '<p class="events-count">' + plural(events.length, 'Termin', 'Termine') +
        (openTotal > 0
            ? ' · <span class="events-count-open">' + plural(openTotal, 'Dienst', 'Dienste') + ' offen</span>'
            : ' · alle Dienste besetzt') +
        '</p>';

    var pdfParams = buildEventParams().toString();

    events.forEach(function (ev, i) {
        var services = ev.services || [];
        var stats = serviceStats(services);
        var delay = Math.min(i * 0.04, 0.8);

        var summary = services.length === 0
            ? 'Keine Dienste eingetragen'
            : stats.accepted + ' von ' + stats.total + ' zugesagt' +
              (stats.pending ? ' · ' + stats.pending + ' ausstehend' : '') +
              (stats.open ? ' · <strong class="summary-open">' + stats.open + ' offen</strong>' : '');

        html += '<section class="service-card" style="animation-delay:' + delay + 's" aria-label="' + escapeHtml(ev.name) + '">' +
            '<header class="service-card-header">' +
                '<div class="event-card-info">' +
                    '<h2 class="event-card-title">' + escapeHtml(ev.name) + '</h2>' +
                    '<span class="event-card-meta">' + escapeHtml(formatDateShort(ev.start_date)) +
                        ' · ' + escapeHtml(ev.calendar_name) + '</span>' +
                    '<span class="service-summary">' + summary + '</span>' +
                '</div>' +
                pdfLink('/api/events/' + ev.id + '/services/pdf?' + pdfParams, ev.name) +
            '</header>';

        if (services.length > 0) {
            html += '<table class="services-table">' +
                '<thead class="sr-only"><tr><th scope="col">Dienst</th><th scope="col">Person</th><th scope="col">Status</th></tr></thead><tbody>';
            services.forEach(function (svc) {
                html += '<tr' + (svc.person_name ? '' : ' class="is-open"') + '>' +
                    '<td class="service-name">' + escapeHtml(svc.name) + '</td>' +
                    '<td class="service-person">' + (svc.person_name
                        ? escapeHtml(svc.person_name)
                        : '<span class="service-unassigned">Nicht besetzt</span>') + '</td>' +
                    '<td class="service-status">' + renderServiceStatus(svc) + '</td>' +
                '</tr>';
            });
            html += '</tbody></table>';
        }
        html += '</section>';
    });

    $('#events-list').innerHTML = html;
}

// --- Load events (shared) ---

// Date changes reload the list (debounced); answers to superseded requests are dropped
var loadTimer = null;
var loadSequence = 0;

function scheduleLoad(delay) {
    clearTimeout(loadTimer);
    loadTimer = setTimeout(loadEvents, delay === undefined ? 400 : delay);
}

function loadEvents() {
    var sequence = ++loadSequence;
    if ($$('.calendar-checkbox:checked').length === 0) {
        showListMessage('Kein Kalender ausgewählt.', 'Wähle unter „Kalender“ mindestens einen aus.', false);
        return;
    }

    $('#events-list').innerHTML =
        '<div class="events-loading">' +
            '<span class="spinner-ring-inline spinner-ring-inline--dark"></span>' +
            '<span>Termine werden geladen&hellip;</span>' +
        '</div>';

    fetch('/api/events?' + buildEventParams().toString())
        .then(function (res) {
            if (res.status === 401) {
                window.location.href = '/';
                return;
            }
            if (!res.ok) throw new Error('Termine konnten nicht geladen werden.');
            return res.json();
        })
        .then(function (data) {
            if (!data || sequence !== loadSequence) return;
            if (getPageMode() === 'services') {
                renderServicesTable(data.events);
            } else {
                renderAgendaEvents(data.events);
            }
        })
        .catch(function (err) {
            if (sequence !== loadSequence) return;
            showListMessage(err.message, 'Bitte prüfe die Verbindung.', true);
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
            scheduleLoad();
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
            scheduleLoad();
        }
    });

    // flatpickr hides the labelled input and shows a generated one; give that one the label
    [[window._fpStart, 'Von'], [window._fpEnd, 'Bis']].forEach(function (entry) {
        if (entry[0] && entry[0].altInput) entry[0].altInput.setAttribute('aria-label', entry[1]);
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

    // Calendar chips toggle (only on pages with calendar selection)
    var calToggle = $('#calendars_toggle');
    if (calToggle) {
        calToggle.addEventListener('click', function () {
            var wrap = $('#calendars_wrap');
            var isExpanded = this.getAttribute('aria-expanded') === 'true';
            wrap.classList.toggle('is-open', !isExpanded);
            this.setAttribute('aria-expanded', isExpanded ? 'false' : 'true');
        });
    }

    // Calendar chip counter
    document.addEventListener('change', function (e) {
        if (e.target.classList.contains('calendar-checkbox')) {
            var total = $$('.calendar-checkbox').length;
            var checked = $$('.calendar-checkbox:checked').length;
            var info = $('.calendar-selection-info');
            if (info) info.textContent = checked + ' von ' + total;
            scheduleLoad(700);
        }
    });

    // Event delegation for agenda card expand/collapse
    var eventsContainer = $('#events-list');
    eventsContainer.addEventListener('click', function (e) {
        if (e.target.closest('[data-action="retry"]')) {
            loadEvents();
            return;
        }
        var header = e.target.closest('.event-card-header');
        if (header) {
            var card = header.closest('.event-card');
            if (card) toggleEventCard(card);
        }
    });

    // Initial load (replaces the loads scheduled by initializing the date pickers)
    scheduleLoad(0);
});
