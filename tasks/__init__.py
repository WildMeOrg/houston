# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,wrong-import-position
"""
The starting point of Invoke tasks for Houston.
"""

import logging
import os
import platform

try:
    import rich
    from rich.logging import RichHandler
    from rich.style import Style
    from rich.theme import Theme

    console_kwargs = {
        'theme': Theme(
            {
                'logging.keyword': Style(bold=True, color='yellow'),
                'logging.level.notset': Style(dim=True),
                'logging.level.debug': Style(color='cyan'),
                'logging.level.info': Style(color='green'),
                'logging.level.warning': Style(color='yellow'),
                'logging.level.error': Style(color='red', bold=True),
                'logging.level.critical': Style(color='red', bold=True, reverse=True),
                'log.time': Style(color='white'),
            }
        )
    }
    handler_kwargs = {
        'rich_tracebacks': True,
        'tracebacks_show_locals': True,
    }
    if os.environ.get('TERM', None) is None:
        try:
            log_width = os.environ.get('LOG_WIDTH', None)
            log_width = float(log_width)
        except Exception:
            log_width = 200

        # Inside docker without TTL
        console_kwargs['force_terminal'] = True
        console_kwargs['force_interactive'] = True
        console_kwargs['width'] = log_width
        console_kwargs['soft_wrap'] = True

    rich.reconfigure(**console_kwargs)
    handler = RichHandler(**handler_kwargs)

    FORMAT = '[%(name)s] %(message)s'
    logging.basicConfig(
        level=logging.DEBUG, format=FORMAT, datefmt='[%X]', handlers=[handler]
    )
except ImportError:  # pragma: no cover
    logging.basicConfig()

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# logging.getLogger('app').setLevel(logging.DEBUG)

from invoke import Collection  # NOQA
from invoke.executor import Executor  # NOQA

namespaces = []
try:
    from tasks import app as app_tasks  # NOQA

    namespaces.append(app_tasks)
except ModuleNotFoundError as e:  # pragma: no cover
    logger.warning(f'Unable to load tasks.app.*\n{str(e)}')

try:
    from tasks import codex as codex_tasks  # NOQA

    namespaces.append(codex_tasks)
except ModuleNotFoundError as e:  # pragma: no cover
    logger.warning(f'Unable to load tasks.codex.*\n{str(e)}')

try:
    from tasks import mws as mws_tasks  # NOQA

    namespaces.append(mws_tasks)
except ModuleNotFoundError as e:  # pragma: no cover
    logger.warning(f'Unable to load tasks.mws.*\n{str(e)}')

from tasks import dependencies as task_dependencies  # NOQA
from tasks import docker_compose as task_docker_compose  # NOQA

namespaces.append(task_dependencies)
namespaces.append(task_docker_compose)

try:
    from tasks import sage as sage_tasks  # NOQA

    namespaces.append(sage_tasks)
except ModuleNotFoundError as e:  # pragma: no cover
    logger.warning(f'Unable to load tasks.sage.*\n{str(e)}')

try:
    from tasks import edm as edm_tasks  # NOQA

    namespaces.append(edm_tasks)
except ModuleNotFoundError as e:  # pragma: no cover
    logger.warning(f'Unable to load tasks.edm.*\n{str(e)}')

try:
    from tasks import gumby as gumby_tasks  # NOQA

    namespaces.append(gumby_tasks)
except ModuleNotFoundError as e:  # pragma: no cover
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
