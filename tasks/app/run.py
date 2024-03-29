# -*- coding: utf-8 -*-
# pylint: disable=too-many-arguments
"""
Application execution related tasks for Invoke.
"""

try:
    from importlib import reload
except ImportError:  # pragma: no cover
    pass  # Python 2 has built-in reload() function
import logging
import os
import platform

from flask_restx_patched import is_extension_enabled
from tasks.utils import app_context_task

log = logging.getLogger(__name__)


DEFAULT_HOST = '0.0.0.0'


def hide_noisy_endpoint_logs():
    """Disable logs for requests to specific endpoints."""
    import re

    from werkzeug import serving

    disabled_endpoints = (
        '/api/v1/site-settings/heartbeat',
        '/api/v1/tus',
    )

    parent_log_request = serving.WSGIRequestHandler.log_request

    def log_request(self, *args, **kwargs):
        if not any(re.match(f'{de}$', self.path) for de in disabled_endpoints):
            parent_log_request(self, *args, **kwargs)

    serving.WSGIRequestHandler.log_request = log_request


def warmup(
    context,
    app,
    host=DEFAULT_HOST,
    install_dependencies=False,
    build_frontend=True,
    upgrade_db=True,
    print_routes=False,
    print_scopes=False,
):
    """
    Pre-configure the Houston API Server before running
    """
    if install_dependencies:
        context.invoke_execute(context, 'dependencies.install-python-dependencies')

    if upgrade_db:
        # After the installed dependencies the app.db.* tasks might need to be
        # reloaded to import all necessary dependencies.
        from tasks.app import db as db_tasks

        reload(db_tasks)

        context.invoke_execute(context, 'app.db.upgrade', app=app, backup=False)

    if is_extension_enabled('elasticsearch'):
        from app.extensions import elasticsearch as es

        es.attach_listeners(app)
        update = app.config.get('ELASTICSEARCH_BUILD_INDEX_ON_STARTUP', False)
        es.es_index_all(app, pit=True, update=update, force=True)

    from app.extensions import prometheus

    prometheus.init(app)

    if print_routes or app.debug:
        log.info('Using route rules:')
        for rule in app.url_map.iter_rules():
            log.info('\t{!r}'.format(rule))

    if print_scopes or app.debug:
        log.info('Using OAuth2 scopes:')
        from app.extensions.api import api_v1

        scopes = sorted(list(api_v1.authorizations['oauth2_password']['scopes'].keys()))
        for scope in scopes:
            log.info('\t{!r}'.format(scope))

    return app


@app_context_task(default=True)
def run(
    context,
    host=DEFAULT_HOST,
    port=5000,
    install_dependencies=False,
    build_frontend=True,
    upgrade_db=True,
    uwsgi=False,
    uwsgi_mode='http',
    uwsgi_extra_options='',
):
    """
    Run Houston API Server.
    """
    from flask import current_app as app

    warmup(
        context,
        app=app,
        host=host,
        install_dependencies=install_dependencies,
        build_frontend=build_frontend,
        upgrade_db=upgrade_db,
    )

    # Turn off logging the access log for noisy endpoints (like the heartbeat)
    hide_noisy_endpoint_logs()

    use_reloader = app.config.get('USE_RELOADER', False)

    if uwsgi:
        uwsgi_args = [
            'uwsgi',
            '--need-app',
            '--manage-script-name',
            '--mount',
            '/=app:create_app()',
            '--%s-socket' % uwsgi_mode,
            '%s:%d' % (host, port),
        ]
        if use_reloader:
            uwsgi_args += ['--python-auto-reload', '2']
        if uwsgi_extra_options:
            uwsgi_args += uwsgi_extra_options.split(' ')
        os.execvpe('uwsgi', uwsgi_args, os.environ)
    else:
        if platform.system() == 'Windows':
            # log.warning(
            #     "Auto-reloader feature doesn't work on Windows. "
            #     'Follow the issue for more details: '
            #     'https://github.com/frol/flask-restplus-server-example/issues/16'
            # )
            use_reloader = False

        exit_code = app.run(host=host, port=port, use_reloader=use_reloader)

        if is_extension_enabled('elasticsearch'):
            from app.extensions import elasticsearch as es

            es.shutdown_celery()

        return exit_code
