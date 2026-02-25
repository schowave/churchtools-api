/* appointments.js - Consolidated JavaScript for the appointments page */

// --- Utility functions (no DOM dependency) ---

function monitorDownload(cookieName) {
    var checkCookie = setInterval(function () {
        if (document.cookie.split(';').some(function (item) {
            return item.trim().startsWith(cookieName + '=');
        })) {
            clearInterval(checkCookie);
            document.cookie = cookieName + '=; Max-Age=-99999999;';
            $('#spinner-overlay').hide();

            document.dispatchEvent(new CustomEvent('cookieChanged', {
                detail: { name: cookieName }
            }));
        }
    }, 100);
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

function showDateChangeMessage() {
    if ($('.appointments-container').length > 0) {
        $('.appointments-container').html(
            '<p>Please click on "Fetch Appointments" to display appointments for the new time period.</p>'
        );
    }
}

function checkAppointments() {
    var hasAppointments = $('.appointment-checkbox').length > 0;

    $('#generate_pdf_btn, #generate_jpeg_btn').prop('disabled', !hasAppointments);

    if (!hasAppointments) {
        $('#generate_error').show();
        $('#generate_pdf_btn, #generate_jpeg_btn').on('click', function (e) {
            if (!hasAppointments) {
                e.preventDefault();
                alert('Bitte holen Sie zuerst Termine ab, bevor Sie eine Ausgabe generieren.');
            }
        });
    } else {
        $('#generate_error').hide();
    }
}

// --- jQuery-dependent initialization ---

$(function () {
    // Datepicker setup
    $("#start_date").datepicker({
        dateFormat: "yy-mm-dd",
        onSelect: function () { showDateChangeMessage(); }
    });
    $("#end_date").datepicker({
        dateFormat: "yy-mm-dd",
        onSelect: function () { showDateChangeMessage(); }
    });

    // Set initial values if not already set
    if (!$("#start_date").val() || !$("#end_date").val()) {
        var thisWeek = calculateThisWeekDates();
        $("#start_date").val($.datepicker.formatDate("yy-mm-dd", thisWeek.start));
        $("#end_date").val($.datepicker.formatDate("yy-mm-dd", thisWeek.end));
    }

    // Date preset buttons
    $("#today").click(function () {
        var today = new Date();
        var formattedDate = $.datepicker.formatDate("yy-mm-dd", today);
        $("#start_date").val(formattedDate);
        $("#end_date").val(formattedDate);
    });

    $("#this-week").click(function () {
        var thisWeek = calculateThisWeekDates();
        $("#start_date").val($.datepicker.formatDate("yy-mm-dd", thisWeek.start));
        $("#end_date").val($.datepicker.formatDate("yy-mm-dd", thisWeek.end));
        showDateChangeMessage();
    });

    $("#next-week").click(function () {
        var nextWeek = calculateNextWeekDates();
        $("#start_date").val($.datepicker.formatDate("yy-mm-dd", nextWeek.start));
        $("#end_date").val($.datepicker.formatDate("yy-mm-dd", nextWeek.end));
        showDateChangeMessage();
    });

    // Spinner monitoring for button clicks
    $('input[name="generate_jpeg"]').click(function () {
        $('#spinner-overlay').show();
        monitorDownload('jpegGenerated');
    });

    $('input[name="generate_pdf"]').click(function () {
        $('#spinner-overlay').show();
        monitorDownload('pdfGenerated');
    });

    $('input[name="fetch_appointments"]').click(function () {
        $('#spinner-overlay').show();
        monitorDownload('fetchAppointments');
        localStorage.setItem('scrollToAppointments', 'true');
    });

    // Scroll to appointments after fetch (if flag is set)
    if ($('.appointments-container').length > 0 && localStorage.getItem('scrollToAppointments') === 'true') {
        localStorage.removeItem('scrollToAppointments');
        setTimeout(function () {
            $('html, body').animate({
                scrollTop: $('.appointments-actions').offset().top - 20
            }, 1000);
        }, 500);
    }

    // Check appointment availability for generate buttons
    checkAppointments();

    // Observe DOM changes in appointments container
    var container = document.querySelector('.appointments-container');
    if (container) {
        var observer = new MutationObserver(checkAppointments);
        observer.observe(container, { childList: true, subtree: true });
    }

    // Select all / deselect all buttons
    var selectAllButton = document.getElementById('selectAllAppointments');
    var deselectAllButton = document.getElementById('deselectAllAppointments');
    var checkboxes = document.querySelectorAll('.appointment-checkbox');

    if (selectAllButton) {
        selectAllButton.addEventListener('click', function () {
            checkboxes.forEach(function (checkbox) { checkbox.checked = true; });
        });
    }

    if (deselectAllButton) {
        deselectAllButton.addEventListener('click', function () {
            checkboxes.forEach(function (checkbox) { checkbox.checked = false; });
        });
    }

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
});

// --- Textarea auto-resize (runs on window load for correct layout calculations) ---

window.addEventListener('load', function () {
    var textareas = document.querySelectorAll('textarea[name^="additional_info_"]');

    textareas.forEach(function (textarea) {
        setTimeout(function () { autoResizeTextarea(textarea); }, 100);

        textarea.addEventListener('input', function () { autoResizeTextarea(this); });
        textarea.addEventListener('focus', function () { autoResizeTextarea(this); });
        textarea.addEventListener('blur', function () { autoResizeTextarea(this); });
    });
});
