# -*- coding: utf-8 -*-
"""
OAuth2 provider setup.

It is based on the code from the example:
https://github.com/lepture/example-oauth2-server

More details are available here:
* http://flask-oauthlib.readthedocs.org/en/latest/oauth2.html
* http://lepture.com/en/2013/create-oauth-server
"""
import flask
from flask import Blueprint, request, flash, send_file
from flask_login import login_user, logout_user, login_required, current_user
import logging
from .util import ensure_admin_exists
from app.modules.users.models import User
from app.modules.assets.models import Asset

from app.modules.auth.views import (
    _url_for,
    _is_safe_url,
)

from .views import (
    HOUSTON_STATIC_ROOT,
    create_session_oauth2_token,
    delete_session_oauth2_token,
    _render_template,
)


log = logging.getLogger(__name__)

backend_blueprint = Blueprint(
    'backend',
    __name__,
    url_prefix='/houston',
    static_folder=HOUSTON_STATIC_ROOT,
)  # pylint: disable=invalid-name


@backend_blueprint.route('/', methods=['GET'])
@ensure_admin_exists
def home(*args, **kwargs):
    # pylint: disable=unused-argument
    """
    This endpoint offers the home page
    """

    from app.version import version as version_houston
    from app.modules.frontend.resources import parse_frontend_versions

    frontend_versions = parse_frontend_versions()
    version_frontend = None
    timestamp_frontend = None
    for frontend_version in frontend_versions:
        if frontend_versions[frontend_version].get('active'):
            version_frontend = frontend_version
            timestamp_frontend = frontend_versions[frontend_version].get('built')

    commit_houston = version_houston.split('.')[-1]
    commit_frontend = version_frontend

    return _render_template(
        'home.jinja2',
        version_houston=version_houston,
        version_frontend=version_frontend,
        timestamp_frontend=timestamp_frontend,
        commit_houston=commit_houston,
        commit_frontend=commit_frontend,
        user=current_user,
    )


@backend_blueprint.route('/login', methods=['POST'])
@ensure_admin_exists
def user_login(email=None, password=None, remember=None, refer=None, *args, **kwargs):
    # pylint: disable=unused-argument
    """
    This endpoint is the landing page for the logged-in user
    """
    if email is None:
        email = request.form.get('email', None)
    if password is None:
        password = request.form.get('password', None)
    if remember is None:
        remember = request.form.get('remember', None)
        remember = remember in ['true', 'on']
    if refer is None:
        refer = flask.request.args.get('next')

    if refer is not None:
        if not _is_safe_url(refer):
            refer = None

    failure_refer = 'backend.home'

    user = User.find(email=email, password=password)

    redirect = _url_for(failure_refer)
    if user is not None:
        if True not in [user.in_alpha, user.in_beta, user.is_staff, user.is_admin]:
            flash(
                'Your login was correct, but Wildbook is in BETA at the moment and is invite-only.',
                'danger',
            )
            redirect = _url_for(failure_refer)
        else:
            status = login_user(user, remember=remember)

            if status:
                # User logged in organically.
                log.info(
                    'Logged in User (remember = %s): %r'
                    % (
                        remember,
                        user,
                    )
                )
                flash('Logged in successfully.', 'success')
                create_session_oauth2_token()

                if refer is not None:
                    redirect = refer
            else:
                flash(
                    'We could not log you in, most likely due to your account being disabled.  Please speak to a staff member.',
                    'danger',
                )
                redirect = _url_for(failure_refer)
    else:
        flash('Username or password unrecognized.', 'danger')
        redirect = _url_for(failure_refer)

    return flask.redirect(redirect)


@backend_blueprint.route('/logout', methods=['GET'])
@login_required
def user_logout(*args, **kwargs):
    # pylint: disable=unused-argument
    """
    This endpoint is the landing page for the logged-in user
    """
    # Delete the Oauth2 token for this session
    log.info('Logging out User: %r' % (current_user,))

    delete_session_oauth2_token()

    logout_user()

    flash('You were successfully logged out.', 'warning')

    return flask.redirect(_url_for('backend.home'))


@backend_blueprint.route('/asset/<code>', methods=['GET'])
# @login_required
@ensure_admin_exists
def asset(code, *args, **kwargs):
    # pylint: disable=unused-argument
    """
    This endpoint is the account page for the logged-in user
    """
    asset = Asset.query.filter_by(code=code).first_or_404()
    return send_file(asset.absolute_filepath, mimetype='image/jpeg')


@backend_blueprint.route('/admin_init', methods=['GET'])
def admin_init(*args, **kwargs):
    log.info('Initializing first run admin user.')
    return _render_template(
        'admin_init.jinja2'
    )
