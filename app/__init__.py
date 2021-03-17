# -*- coding: utf-8 -*-
"""
Houston API Server.
"""
import os
import sys

from flask import Flask
from werkzeug.contrib.fixers import ProxyFix
import logging
from config import BaseConfig


log = logging.getLogger(__name__)


CONFIG_NAME_MAPPER = {
    'development': 'config.DevelopmentConfig',
    'testing': 'config.TestingConfig',
    'production': 'config.ProductionConfig',
    'local': os.getenv('FLASK_CONFIG_IMPORT', 'local_config.LocalConfig'),
}


def _ensure_storage(app=None):
    # Ensure database submissions and asset store
    config_list = [
        ('DB', 'PROJECT_DATABASE_PATH'),
        ('Submission', 'SUBMISSIONS_DATABASE_PATH'),
        ('FileUpload', 'FILEUPLOAD_BASE_PATH'),
        ('Asset', 'ASSET_DATABASE_PATH'),
    ]

    for config_label, config_name in config_list:
        if app is None:
            path = getattr(BaseConfig, config_name, None)
        else:
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


def configure_from_config_file(app, flask_config_name=None):
    env_flask_config_name = os.getenv('FLASK_CONFIG')
    if not env_flask_config_name and flask_config_name is None:
        flask_config_name = 'local'
    elif flask_config_name is None:
        flask_config_name = env_flask_config_name
    else:
        if env_flask_config_name:
            assert env_flask_config_name == flask_config_name, (
                'FLASK_CONFIG environment variable ("%s") and flask_config_name argument '
                '("%s") are both set and are not the same.'
                % (env_flask_config_name, flask_config_name)
            )

    try:
        config_name = CONFIG_NAME_MAPPER[flask_config_name]
        log.info('Using app.config %r' % (config_name,))
        app.config.from_object(config_name)
    except ImportError:
        if flask_config_name == 'local':
            app.logger.error(  # pylint: disable=no-member
                'You have to have `local_config.py` or `local_config/__init__.py` in order to use '
                "the default 'local' Flask Config. Alternatively, you may set `FLASK_CONFIG` "
                'environment variable to one of the following options: development, production, '
                'testing.'
            )
            sys.exit(1)
        raise


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


def configure_using_houston_flask_config(app):
    from app.extensions.config import HoustonFlaskConfig

    houston_flask_config = HoustonFlaskConfig(app.root_path)
    houston_flask_config.from_mapping(app.config)
    app.config = houston_flask_config


def create_app(flask_config_name=None, config_override={}, testing=False, **kwargs):
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
    configure_from_config_file(app, flask_config_name)

    # Update app config from create_app arguments (passed from CLI)
    configure_from_cli(app, config_override)

    # Replace app.config (flask.Config) with our HoustonFlaskConfig version
    configure_using_houston_flask_config(app)

    if testing:
        return app

    # Initialize all extensions
    from . import extensions

    extensions.init_app(app)

    # Ensure on disk storage
    _ensure_storage(app)

    # Initialize all modules
    from . import modules

    modules.init_app(app)

    # Configure reverse proxy
    if app.config['REVERSE_PROXY_SETUP']:
        app.wsgi_app = ProxyFix(app.wsgi_app)

    return app


# Do this on import as well
_ensure_storage()
