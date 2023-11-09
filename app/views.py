from io import BytesIO

import requests
from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, flash, make_response, \
    session

from config import Config
from .utils import get_login_token, get_date_range_from_form, fetch_appointments, appointment_to_dict
from .pdf_generator import create_pdf

main_bp = Blueprint('main_bp', __name__)


@main_bp.route('/appointments', methods=['GET', 'POST'])
def appointments():
    login_token = get_login_token()
    if not login_token:
        flash('You need to login first.', 'warning')
        return redirect(url_for('main_bp.login'))
    start_date, end_date = get_date_range_from_form()

    if request.method == 'POST' and 'fetch_appointments' in request.form:
        appointments = fetch_appointments(login_token, start_date, end_date)

        session['fetched_appointments'] = [appointment_to_dict(app) for app in appointments]
        return render_template('appointments.html', appointments=session['fetched_appointments'], start_date=start_date,
                               end_date=end_date)

    if request.method == 'POST' and 'generate_pdf' in request.form:
        selected_appointment_ids = request.form.getlist('appointment_id')
        background_image_stream = None
        if 'background_image' in request.files:
            file = request.files['background_image']
            if file and file.filename != '':
                background_image_stream = BytesIO(file.read())
        selected_appointments = [app for app in session.get('fetched_appointments', []) if
                                 str(app['id']) in selected_appointment_ids]
        filename = create_pdf(selected_appointments, background_image_stream)
        return redirect(url_for('main_bp.download_file', filename=filename))

    # This else clause is for when there's no GET or POST, which shouldn't normally happen
    else:
        return render_template('appointments.html', start_date=start_date, end_date=end_date)


@main_bp.route('/', methods=['GET', 'POST'])
def login():
    login_token = get_login_token()
    if login_token:
        return redirect(url_for('main_bp.overview'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        data = {"password": password, "rememberMe": True, "username": username}
        response = requests.post(f'{Config.CHURCHTOOLS_BASE_URL}/api/login', json=data)

        if response.status_code == 200:
            person_id = response.json()['data']['personId']
            token_response = requests.get(f'{Config.CHURCHTOOLS_BASE_URL}/api/persons/{person_id}/logintoken',
                                          cookies=response.cookies)

            if token_response.status_code == 200:
                login_token = token_response.json()['data']
                resp = make_response(redirect(url_for('main_bp.overview')))
                resp.set_cookie('login_token', login_token)
                return resp
            else:
                flash('Failed to retrieve login token.', 'error')
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')
    pass


@main_bp.route('/logout', methods=['POST'])
def logout():
    resp = make_response(redirect(url_for('main_bp.overview')))
    resp.set_cookie('login_token', '', expires=0)  # Clear the login_token cookie
    return resp
    pass


@main_bp.route('/overview')
def overview():
    login_token = get_login_token()
    if not login_token:
        return redirect(url_for('main_bp.login'))

    # Add any additional data you want to pass to your template
    return render_template('overview.html')
    pass


@main_bp.route('/download/<filename>')
def download_file(filename):
    # Use the safe directory when sending the file
    try:
        return send_from_directory(Config.FILE_DIRECTORY, filename, as_attachment=True)
    except FileNotFoundError:
        flash('File not found.', 'error')
        return redirect(url_for('main_bp.appointments'))  # Redirect to appointments page or a 404 page
    pass
