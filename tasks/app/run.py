# -*- coding: utf-8 -*-
# pylint: disable=too-many-arguments
"""
Application execution related tasks for Invoke.
"""

try:
    from importlib import reload
except ImportError:
    pass  # Python 2 has built-in reload() function
import os
import platform
import logging

try:
    from invoke import ctask as task
except ImportError:  # Invoke 0.13 renamed ctask to task
    from invoke import task

from ._utils import app_context_task


log = logging.getLogger(__name__)


DEFAULT_HOST = '0.0.0.0'


@app_context_task()
def warmup(
    context,
    host=DEFAULT_HOST,
    flask_config=None,
    install_dependencies=False,
    build_frontend=True,
    upgrade_db=True,
):
    """
    Pre-configure the Houston API Server before running
    """
    if flask_config is not None:
        os.environ['FLASK_CONFIG'] = flask_config

    if install_dependencies:
        context.invoke_execute(context, 'app.dependencies.install')

    from app import create_app

    app = create_app()

    if upgrade_db:
        # After the installed dependencies the app.db.* tasks might need to be
        # reloaded to import all necessary dependencies.
        from tasks.app import db as db_tasks

        reload(db_tasks)

        context.invoke_execute(context, 'app.db.upgrade', app=app, backup=False)

        # if app.debug:
        #     context.invoke_execute(
        #         context,
        #         'app.db.init_development_data',
        #         app=app,
        #         upgrade_db=False,
        #         skip_on_failure=True,
        #     )

    return app


@task(default=True)
def run(
    context,
    host=DEFAULT_HOST,
    port=5000,
    flask_config=None,
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
    app = warmup(
        context,
        host,
        flask_config=flask_config,
        install_dependencies=install_dependencies,
        build_frontend=build_frontend,
        upgrade_db=upgrade_db,
    )

    # use_reloader = app.debug
    use_reloader = False
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
            log.warning(
                "Auto-reloader feature doesn't work on Windows. "
                'Follow the issue for more details: '
                'https://github.com/frol/flask-restplus-server-example/issues/16'
            )
            use_reloader = False
        return app.run(host=host, port=port, use_reloader=use_reloader)
