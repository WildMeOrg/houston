# -*- coding: utf-8 -*-
"""
Houston API Server.
"""
import functools
import logging
import os

from app.modules import is_module_enabled
from celery import Celery
from flask import Flask
import sqlalchemy
from werkzeug.contrib.fixers import ProxyFix

from config import configure_app


log = logging.getLogger(__name__)


def _ensure_storage(app):
    # Ensure database submissions and asset store
    config_list = [
        ('DB', 'PROJECT_DATABASE_PATH'),
        ('FileUpload', 'FILEUPLOAD_BASE_PATH'),
    ]

    if is_module_enabled('asset_groups'):
        config_list += [
            ('AssetGroup', 'ASSET_GROUP_DATABASE_PATH'),
        ]

    if is_module_enabled('missions'):
        config_list += [
            ('MissionCollection', 'MISSION_COLLECTION_DATABASE_PATH'),
        ]

    for config_label, config_name in config_list:
        path = app.config.get(config_name, None)
        if path is not None and not os.path.exists(path):
            print(
                'Creating %s path: %r'
                % (
                    config_label,
                    path,
                )
            )
            os.mkdir(path)


def _apply_hotfixes():
    # This is a workaround for Alpine Linux (musl libc) quirk:
    # https://github.com/docker-library/python/issues/211
    import threading

    threading.stack_size(2 * 1024 * 1024)


def _ensure_oauth_user(config):
    oauth_user = config.get('OAUTH_USER', None)
    if oauth_user:
        oauth_user = oauth_user.copy()
        client_id = oauth_user.pop('client_id')
        client_secret = oauth_user.pop('client_secret')

        from app.modules.auth.utils import create_session_oauth2_client
        from app.modules.users.models import User

        try:
            user = User.ensure_user(send_verification=False, **oauth_user)
        except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.ProgrammingError):
            # sqlite3.OperationalError no such table
            # sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable) relation "user" does not exist
            # skip oauth user creation if table doesn't exist
            # (happens in app.swagger.export task)
            return
        kwargs = {}
        if client_id and client_secret:
            kwargs = {'guid': client_id, 'secret': client_secret}
        create_session_oauth2_client(user, **kwargs)


def configure_from_cli(app, config_override):
    blacklist = [
        'EDM_AUTHENTICATIONS',
    ]

    for key in config_override:
        value = config_override[key]
        app.config[key] = value

        if key in blacklist:
            value = '<REDACTED>'

        log.warning(
            'CONFIG CLI OVERRIDE: key=%r value=%r'
            % (
                key,
                value,
            )
        )


def create_app(
    config_override={},
    testing=False,
    context=None,
    environment=None,
    force_enable=False,
    force_disable_extensions=None,
    force_disable_modules=None,
    **kwargs
):
    """
    Entry point to the Houston Server application.

    Configuration is loaded in the following order:
        1. On disk configuration in config.py
        2. Command line argument overrides
        3. Database key-value overrides
    """
    _apply_hotfixes()

    app = Flask(__name__, **kwargs)

    # Initialize app config from config.py
    configure_app(app, context=context, environment=environment)

    # Update app config from create_app arguments (passed from CLI)
    configure_from_cli(app, config_override)

    # Set up celery using redis as the broker and result backend
    # Use the same redis instance as tus but use database "1"
    redis_uri = app.config['REDIS_CONNECTION_STRING']
    app.celery = Celery('houston', broker=redis_uri, backend=redis_uri)
    app.url_map.strict_slashes = False
    # celery.conf.update(app.config)

    class ContextTask(app.celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    app.celery.Task = ContextTask

    if testing:
        return app

    if force_enable:
        log.warning('Forcing all extensions and modules (force_enable=True)')

    # Initialize all extensions
    from . import extensions

    extensions.init_app(
        app, force_enable=force_enable, force_disable=force_disable_extensions
    )

    # Ensure on disk storage
    _ensure_storage(app)

    # Initialize all modules
    from . import modules

    modules.init_app(app, force_enable=force_enable, force_disable=force_disable_modules)

    # Configure reverse proxy
    if app.config['REVERSE_PROXY_SETUP']:
        app.wsgi_app = ProxyFix(app.wsgi_app)

    # Ensure oauth user after the app is initialized, before the first
    # request
    app.before_first_request(functools.partial(_ensure_oauth_user, app.config))

    return app
