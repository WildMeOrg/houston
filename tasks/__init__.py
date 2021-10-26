# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,wrong-import-position
"""
The starting point of Invoke tasks for Houston.
"""

import logging
import os
import platform

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# logging.getLogger('app').setLevel(logging.DEBUG)

try:
    import colorlog
except ImportError:  # pragma: no cover
    pass
else:
    formatter = colorlog.ColoredFormatter(
        (
            '%(asctime)s '
            '[%(log_color)s%(levelname)s%(reset)s] '
            '[%(cyan)s%(name)s%(reset)s] '
            '%(message_log_color)s%(message)s'
        ),
        reset=True,
        log_colors={
            'DEBUG': 'bold_cyan',
            'INFO': 'bold_green',
            'WARNING': 'bold_yellow',
            'ERROR': 'bold_red',
            'CRITICAL': 'bold_red,bg_white',
        },
        secondary_log_colors={
            'message': {
                'DEBUG': 'white',
                'INFO': 'bold_white',
                'WARNING': 'bold_yellow',
                'ERROR': 'bold_red',
                'CRITICAL': 'bold_red',
            },
        },
        style='%',
    )

    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            break
    else:
        handler = logging.StreamHandler()
        logger.addHandler(handler)
    handler.setFormatter(formatter)


from invoke import Collection  # NOQA
from invoke.executor import Executor  # NOQA

namespaces = []
try:
    from tasks import app as app_tasks  # NOQA

    namespaces.append(app_tasks)
except ModuleNotFoundError as e:
    logger.warning(f'Unable to load tasks.app.*\n{str(e)}')

try:
    from tasks import codex as codex_tasks  # NOQA

    namespaces.append(codex_tasks)
except ModuleNotFoundError as e:
    logger.warning(f'Unable to load tasks.codex.*\n{str(e)}')

try:
    from tasks import mws as mws_tasks  # NOQA

    namespaces.append(mws_tasks)
except ModuleNotFoundError as e:
    logger.warning(f'Unable to load tasks.mws.*\n{str(e)}')

from tasks import dependencies as task_dependencies  # NOQA
from tasks import docker_compose as task_docker_compose  # NOQA

namespaces.append(task_dependencies)
namespaces.append(task_docker_compose)

try:
    from tasks import gumby as gumby_tasks  # NOQA

    namespaces.append(gumby_tasks)
except ModuleNotFoundError as e:
    logger.warning(f'Unable to load tasks.gumby.*\n{str(e)}')

# NOTE: `namespace` or `ns` name is required!
namespace = Collection(*namespaces)


def invoke_execute(context, command_name, **kwargs):
    """
    Helper function to make invoke-tasks execution easier.
    """
    results = Executor(namespace, config=context.config).execute((command_name, kwargs))
    target_task = context.root_namespace[command_name]
    return results[target_task]


namespace.configure(
    {
        'run': {
            'shell': '/bin/sh'
            if platform.system() != 'Windows'
            else os.environ.get('COMSPEC'),
        },
        'root_namespace': namespace,
        'invoke_execute': invoke_execute,
    }
)
