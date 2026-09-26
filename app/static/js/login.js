/* login.js — show/hide password and a busy state while ChurchTools checks the login */

document.addEventListener('DOMContentLoaded', function () {
    var password = document.getElementById('password');
    var toggle = document.getElementById('password_toggle');
    var form = document.getElementById('login_form');
    var submit = document.getElementById('login_submit');

    // The toggle only works with JS, so it stays hidden without it
    toggle.hidden = false;
    toggle.addEventListener('click', function () {
        var show = password.type === 'password';
        password.type = show ? 'text' : 'password';
        toggle.textContent = show ? 'Verbergen' : 'Anzeigen';
        toggle.setAttribute('aria-pressed', show ? 'true' : 'false');
        password.focus();
    });

    form.addEventListener('submit', function (e) {
        if (submit.disabled) {
            e.preventDefault();
            return;
        }
        // Never submit a visible password field (browsers may remember it as plain text)
        password.type = 'password';
        submit.disabled = true;
        submit.querySelector('.btn-label').hidden = true;
        submit.querySelector('.btn-spinner').hidden = false;
    });

    // Back/forward cache: a restored page must not stay in the busy state
    window.addEventListener('pageshow', function () {
        submit.disabled = false;
        submit.querySelector('.btn-label').hidden = false;
        submit.querySelector('.btn-spinner').hidden = true;
    });
});
