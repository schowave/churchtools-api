/* appointments.js - Consolidated JavaScript for the appointments page */

// --- Utility functions (no DOM dependency) ---

function monitorDownload(cookieName, $btn) {
    var checkCookie = setInterval(function () {
        if (document.cookie.split(';').some(function (item) {
            return item.trim().startsWith(cookieName + '=');
        })) {
            clearInterval(checkCookie);
            document.cookie = cookieName + '=; Max-Age=-99999999;';
            if ($btn) {
                $btn.removeClass('is-loading');
                $btn.find('.btn-label').show();
                $btn.find('.btn-spinner').hide();
            }

            document.dispatchEvent(new CustomEvent('cookieChanged', {
                detail: { name: cookieName }
            }));
        }
    }, 100);
}

function showButtonSpinner($btn) {
    $btn.addClass('is-loading');
    $btn.find('.btn-label').hide();
    $btn.find('.btn-spinner').show();
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

// --- Appointment rendering ---

function renderAppointments(appointments) {
    var $main = $('.appointments-main');

    if (!appointments || appointments.length === 0) {
        $main.html(
            '<div class="empty-state">' +
                '<p>Keine Termine vorhanden.</p>' +
                '<p class="empty-state-hint">Bitte Datum und Kalender auswählen und "Termine abholen" klicken.</p>' +
            '</div>'
        );
        checkAppointments();
        return;
    }

    var html = '<div class="appointments-actions">' +
        '<span class="appointment-count">' + appointments.length + ' von ' + appointments.length + ' ausgewählt</span>' +
        '<button type="button" id="selectAllAppointments" class="select-all-btn">Alle auswählen</button>' +
        '<button type="button" id="deselectAllAppointments" class="deselect-all-btn">Alle abwählen</button>' +
        '</div>' +
        '<div class="appointments-container">';

    appointments.forEach(function (app) {
        var hasInfo = app.additional_info && app.additional_info.trim().length > 0;
        html += '<div class="appointment-item">' +
            '<input type="checkbox" id="appointment-' + escapeHtml(app.id) + '" name="appointment_id"' +
            ' value="' + escapeHtml(app.id) + '" class="appointment-checkbox" checked>' +
            '<label for="appointment-' + escapeHtml(app.id) + '" class="appointment-label">' +
                '<span class="appointment-date">' +
                    escapeHtml(app.start_date_view) +
                    ' (' + escapeHtml(app.start_time_view) + '-' + escapeHtml(app.end_time_view) + ')' +
                '</span>' +
                '<span class="appointment-description">' + escapeHtml(app.title) + '</span>' +
            '</label>' +
            '<button type="button" class="add-info-toggle' + (hasInfo ? ' hidden' : '') + '"' +
                ' onclick="this.classList.add(\'hidden\'); this.nextElementSibling.classList.remove(\'hidden\'); this.nextElementSibling.focus();">' +
                '+ Info hinzufügen' +
            '</button>' +
            '<textarea name="additional_info_' + escapeHtml(app.id) + '"' +
                ' class="' + (hasInfo ? '' : 'hidden') + '"' +
                ' placeholder="Zusätzliche Informationen">' + escapeHtml(app.additional_info || '') + '</textarea>' +
            '</div>';
    });

    html += '</div>';
    $main.html(html);

    // Rebind select/deselect buttons
    $('#selectAllAppointments').on('click', function () {
        $('.appointment-checkbox').prop('checked', true);
        updateSelectionCount();
    });
    $('#deselectAllAppointments').on('click', function () {
        $('.appointment-checkbox').prop('checked', false);
        updateSelectionCount();
    });

    // Auto-resize textareas
    $main.find('textarea').each(function () {
        var textarea = this;
        setTimeout(function () { autoResizeTextarea(textarea); }, 50);
        $(textarea).on('input focus blur', function () { autoResizeTextarea(this); });
    });

    checkAppointments();
}

function fetchAppointmentsAjax() {
    var startDate = $('#start_date').val();
    var endDate = $('#end_date').val();
    var calendarIds = [];
    $('.calendar-checkbox:checked').each(function () {
        calendarIds.push($(this).val());
    });

    // Show loading state
    var $fetchBtn = $('#fetch_btn');
    showButtonSpinner($fetchBtn);
    $('.appointments-main').html(
        '<div class="appointments-loading">' +
            '<span class="spinner-ring-inline spinner-ring-inline--dark"></span>' +
            '<span>Termine werden geladen…</span>' +
        '</div>'
    );

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
            // Reset fetch button
            $fetchBtn.removeClass('is-loading');
            $fetchBtn.find('.btn-label').show();
            $fetchBtn.find('.btn-spinner').hide();
        })
        .catch(function (err) {
            $('.appointments-main').html(
                '<div class="empty-state">' +
                    '<p>' + escapeHtml(err.message) + '</p>' +
                '</div>'
            );
            $fetchBtn.removeClass('is-loading');
            $fetchBtn.find('.btn-label').show();
            $fetchBtn.find('.btn-spinner').hide();
        });
}

function updateSelectionCount() {
    var total = $('.appointment-checkbox').length;
    var checked = $('.appointment-checkbox:checked').length;
    $('.appointment-count').text(checked + ' von ' + total + ' ausgewählt');
}

function checkAppointments() {
    var hasAppointments = $('.appointment-checkbox').length > 0;

    $('#generate_pdf_btn, #generate_jpeg_btn').prop('disabled', !hasAppointments);

    if (!hasAppointments) {
        $('#generate_error').show();
    } else {
        $('#generate_error').hide();
    }
}

// --- jQuery-dependent initialization ---

$(function () {
    // Datepicker setup — display dd.mm.yy, store yy-mm-dd in hidden fields
    $("#start_date_display").datepicker({
        dateFormat: "dd.mm.yy",
        altField: "#start_date",
        altFormat: "yy-mm-dd"
    });
    $("#end_date_display").datepicker({
        dateFormat: "dd.mm.yy",
        altField: "#end_date",
        altFormat: "yy-mm-dd"
    });

    // Initialize display fields from hidden ISO values
    var startIso = $("#start_date").val();
    var endIso = $("#end_date").val();
    if (startIso) {
        var startParts = startIso.split("-");
        $("#start_date_display").val(startParts[2] + "." + startParts[1] + "." + startParts[0]);
    }
    if (endIso) {
        var endParts = endIso.split("-");
        $("#end_date_display").val(endParts[2] + "." + endParts[1] + "." + endParts[0]);
    }

    // Set defaults if no values provided
    if (!startIso || !endIso) {
        var thisWeek = calculateThisWeekDates();
        $("#start_date_display").datepicker("setDate", thisWeek.start);
        $("#end_date_display").datepicker("setDate", thisWeek.end);
    }

    // Date preset buttons — set datepicker (auto-syncs to hidden field) then fetch
    $("#today").click(function () {
        var today = new Date();
        $("#start_date_display").datepicker("setDate", today);
        $("#end_date_display").datepicker("setDate", today);
        fetchAppointmentsAjax();
    });

    $("#this-week").click(function () {
        var thisWeek = calculateThisWeekDates();
        $("#start_date_display").datepicker("setDate", thisWeek.start);
        $("#end_date_display").datepicker("setDate", thisWeek.end);
        fetchAppointmentsAjax();
    });

    $("#next-week").click(function () {
        var nextWeek = calculateNextWeekDates();
        $("#start_date_display").datepicker("setDate", nextWeek.start);
        $("#end_date_display").datepicker("setDate", nextWeek.end);
        fetchAppointmentsAjax();
    });

    // Fetch button — AJAX, no form submit
    $('#fetch_btn').click(function () {
        fetchAppointmentsAjax();
    });

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

    // Live selection counter (delegated for dynamically added checkboxes)
    $(document).on('change', '.appointment-checkbox', updateSelectionCount);

    // Logo upload - button triggers hidden file input
    $('#logo_upload_btn').on('click', function () {
        document.getElementById('logo_upload').click();
    });

    $('#logo_upload').on('change', function () {
        var file = this.files[0];
        if (!file) return;
        var formData = new FormData();
        formData.append('file', file);
        var $btn = $('#logo_upload_btn');
        showButtonSpinner($btn);
        fetch('/logo/upload', { method: 'POST', body: formData })
            .then(function (res) {
                if (!res.ok) return res.text().then(function (t) { throw new Error('Upload fehlgeschlagen: ' + t); });
                return res.json();
            })
            .then(function () {
                $('#logo-img').attr('src', '/logo?' + Date.now());
                $('#logo-preview').show();
                $('#logo_delete').show();
                $btn.removeClass('is-loading');
                $btn.find('.btn-spinner').hide();
                $btn.find('.btn-label').text('Logo gespeichert!').show();
                setTimeout(function () { $btn.find('.btn-label').text('Logo hochladen'); }, 2000);
            })
            .catch(function (err) {
                alert(err.message);
                $btn.removeClass('is-loading');
                $btn.find('.btn-spinner').hide();
                $btn.find('.btn-label').show();
            });
        this.value = '';
    });

    // Logo delete
    $('#logo_delete').on('click', function () {
        fetch('/logo', { method: 'DELETE' })
            .then(function (res) {
                if (!res.ok) return res.text().then(function (t) { throw new Error('Löschen fehlgeschlagen: ' + t); });
                $('#logo-preview').hide();
                $('#logo_delete').hide();
            })
            .catch(function (err) { alert(err.message); });
    });

    // Background image upload - button triggers hidden file input
    $('#bg_upload_btn').on('click', function () {
        document.getElementById('bg_upload').click();
    });

    $('#bg_upload').on('change', function () {
        var file = this.files[0];
        if (!file) return;
        var formData = new FormData();
        formData.append('file', file);
        var $btn = $('#bg_upload_btn');
        showButtonSpinner($btn);
        fetch('/background/upload', { method: 'POST', body: formData })
            .then(function (res) {
                if (!res.ok) return res.text().then(function (t) { throw new Error('Upload fehlgeschlagen: ' + t); });
                return res.json();
            })
            .then(function () {
                $('#bg-img').attr('src', '/background?' + Date.now());
                $('#bg-preview').show();
                $('#bg_delete').show();
                $btn.removeClass('is-loading');
                $btn.find('.btn-spinner').hide();
                $btn.find('.btn-label').text('Bild gespeichert!').show();
                setTimeout(function () { $btn.find('.btn-label').text('Bild hochladen'); }, 2000);
            })
            .catch(function (err) {
                alert(err.message);
                $btn.removeClass('is-loading');
                $btn.find('.btn-spinner').hide();
                $btn.find('.btn-label').show();
            });
        this.value = '';
    });

    // Background image delete
    $('#bg_delete').on('click', function () {
        fetch('/background', { method: 'DELETE' })
            .then(function (res) {
                if (!res.ok) return res.text().then(function (t) { throw new Error('Löschen fehlgeschlagen: ' + t); });
                $('#bg-preview').hide();
                $('#bg_delete').hide();
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
                document.getElementById('alphaValue').textContent = presets[selectedPreset].background_alpha;
            }
        });
    }

    // Initial button state
    checkAppointments();

    // Auto-fetch appointments on page load
    fetchAppointmentsAjax();
});
