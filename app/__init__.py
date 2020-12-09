# -*- coding: utf-8 -*-
"""
Houston API Server.
"""
import os
import sys

from flask import Flask
from werkzeug.contrib.fixers import ProxyFix
import logging

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

log = logging.getLogger(__name__)


CONFIG_NAME_MAPPER = {
    'development': 'config.DevelopmentConfig',
    'testing': 'config.TestingConfig',
    'production': 'config.ProductionConfig',
    'local': 'local_config.LocalConfig',
}


def create_app(flask_config_name=None, config_override={}, **kwargs):
    """
    Entry point to the Houston Server application.
    """
    # This is a workaround for Alpine Linux (musl libc) quirk:
    # https://github.com/docker-library/python/issues/211
    import threading

    threading.stack_size(2 * 1024 * 1024)

    app = Flask(__name__, **kwargs)

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

    app.config.update(config_override)

    for key in config_override:
        value = config_override[key]
        print(
            'CONFIG OVERRIDE %r -> %r'
            % (
                key,
                value,
            )
        )

    # if specified, setup sentry for exception reporting and runtime telemetry
    sentry_dsn = app.config.get('SENTRY_DSN', None)
    if sentry_dsn is not None:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FlaskIntegration()],
        )

    if app.config['REVERSE_PROXY_SETUP']:
        app.wsgi_app = ProxyFix(app.wsgi_app)

    from . import extensions

    extensions.init_app(app)

    from . import modules

    modules.init_app(app)

    return app
