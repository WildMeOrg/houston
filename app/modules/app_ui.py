# -*- coding: utf-8 -*-
"""Provides UI space served directly from this application"""
import datetime
import logging
from functools import wraps

# from app.modules.users.permissions import PasswordRequiredPermissionMixin
import flask
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app.modules.auth.utils import (
    create_session_oauth2_token,
    delete_session_oauth2_token,
)
from app.modules.auth.views import _is_safe_url
from app.modules.users.models import User

log = logging.getLogger(__name__)

frontend_blueprint = Blueprint('frontend', __name__)
backend_blueprint = Blueprint(
    'backend',
    __name__,
    url_prefix='/houston',
)  # pylint: disable=invalid-name


def init_app(app):
    backend_blueprint.static_folder = app.config['STATIC_ROOT']
    app.register_blueprint(frontend_blueprint)
    app.register_blueprint(backend_blueprint)


@frontend_blueprint.route('/', endpoint='root')
@frontend_blueprint.route('/login', endpoint='login')
@frontend_blueprint.route('/auth/code/<string:code>', endpoint='auth-code')
@frontend_blueprint.route(
    '/pending-sightings/<string:guid>', endpoint='pending-sightings'
)
@frontend_blueprint.route('/sightings/<string:guid>', endpoint='sightings')
def dummy_view(*args, **kwargs):
    """This view is created just for frontend route generation"""
    raise NotImplementedError


def _render_template(template, **kwargs):
    now = datetime.datetime.now(tz=current_app.config.get('TIMEZONE'))
    config = {
        'base_url': url_for('frontend.root'),
        'google_analytics_tag': current_app.config.get('GOOGLE_ANALYTICS_TAG'),
        'stripe_public_key': current_app.config.get('STRIPE_PUBLIC_KEY'),
        'year': now.year,
        'cachebuster': '20200322-0',
    }
    config.update(kwargs)
    return render_template(template, **config)


def ensure_admin_exists(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user and not User.admin_user_initialized():
            return redirect(url_for('backend.admin_init'))
        return func(*args, **kwargs)

    return decorated_function


def admin_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user and not current_user.is_admin:
            return redirect(url_for('backend.user_login'))
        return func(*args, **kwargs)

    return decorated_function


@backend_blueprint.route('/', methods=['GET'])
@ensure_admin_exists
def home(*args, **kwargs):
    # pylint: disable=unused-argument
    """
    This endpoint offers the home page
    """
    from app.version import version

    commit_houston = version.split('.')[-1]

    return _render_template(
        'home.jinja2',
        version_houston=version,
        commit_houston=commit_houston,
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
            log.error('User gave insecure next URL: {!r}'.format(refer))
            refer = None

    failure_refer = 'backend.home'

    user = User.find(email=email, password=password)

    redirect = url_for(failure_refer)
    if user is not None:
        if True not in [user.in_alpha, user.in_beta, user.is_staff, user.is_admin]:
            flash(
                'Your login was correct, but Wildbook is in BETA at the moment and is invite-only.',
                'danger',
            )
            redirect = url_for(failure_refer)
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
                redirect = url_for(failure_refer)
    else:
        flash('Username or password unrecognized.', 'danger')
        redirect = url_for(failure_refer)

    return flask.redirect(redirect)


@backend_blueprint.route('/logout', methods=['GET', 'POST'])
@frontend_blueprint.route('/logout', methods=['GET', 'POST'])
@login_required
def user_logout(refer=None, *args, **kwargs):
    # pylint: disable=unused-argument
    """
    This endpoint is the landing page for the logged-in user
    """
    if refer is None:
        refer = flask.request.args.get('next', request.form.get('next', None))

    if refer in ['origin']:
        refer = request.referrer

    if refer is not None:
        if not _is_safe_url(refer):
            log.error('User gave insecure next URL: {!r}'.format(refer))
            refer = None

    # Delete the Oauth2 token for this session
    log.info('Logging out User: {!r}'.format(current_user))

    delete_session_oauth2_token()

    logout_user()

    flash('You were successfully logged out.', 'warning')

    if refer is None:
        redirect = url_for('backend.home')
    else:
        redirect = refer

    return flask.redirect(redirect)


@backend_blueprint.route('/admin_init', methods=['GET'])
def admin_init(*args, **kwargs):
    """
    This endpoint is for initial admin user creation
    """
    return _render_template(
        'home.admin_init.jinja2', admin_exists=User.admin_user_initialized()
    )


@backend_blueprint.route('/admin_init', methods=['POST'])
def create_admin_user(email=None, password=None, repeat_password=None, *args, **kwargs):
    """
    This endpoint creates the initial admin user if none exists
    """
    message = None

    if User.admin_user_initialized():
        message = 'This function is disabled. Admin user exists.'
    else:
        log.info('Attempting to create first run admin user.')
        if email is None:
            email = request.form.get('email', None)
        if password is None:
            password = request.form.get('password', None)
        if repeat_password is None:
            repeat_password = request.form.get('repeat_password', None)

        if password == repeat_password:
            if None not in [email, password, repeat_password]:
                admin = User.ensure_user(
                    email,
                    password,
                    is_admin=True,
                    update=True,
                )
                if admin.is_admin:
                    message = 'Success creating startup admin user.'
                    # update configuration value for admin user created
                    return flask.redirect(url_for('backend.home'))
                else:
                    message = 'We failed to create or update the user as an admin.'
            else:
                message = 'You must specify all fields.'
        else:
            message = 'The password fields do not match.'

    if message is not None:
        flash(message)


@backend_blueprint.route('/internal/testing', methods=['GET'])
@login_required
@admin_required
def internal_testing(*args, **kwargs):
    """
    This endpoint is for internal testing
    """
    return _render_template(
        'internal.testing.jinja2',
        user=current_user,
    )


@backend_blueprint.route('/internal/testing/logging', methods=['GET'])
def log_testing(*args, **kwargs):
    """
    This endpoint is for internal logging testing
    """
    import app.extensions.logging as AuditLog

    log.info('A test INFO message')
    log.debug('A test DEBUG message')
    log.warning('A test WARNING message')
    log.error('A test ERROR message')
    log.critical('A test CRITICAL message')

    AuditLog.audit_log(log, 'A test AUDIT log message')

    try:
        try:
            assert False, 'A test EXCEPTION message'
        except AssertionError as ex:
            log.exception(ex)
    except Exception:
        pass

    return home()
