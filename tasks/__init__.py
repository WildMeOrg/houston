# -*- coding: utf-8 -*-
# pylint: disable=invalid-name,wrong-import-position
"""
The starting point of Invoke tasks for Houston.
"""

import logging
import logging.handlers
import platform

from config.utils import _getenv

FORMAT = '[%(name)s] %(message)s'
logging_config = {'level': logging.DEBUG, 'format': FORMAT, 'datefmt': '[%X]'}
handlers = [
    logging.handlers.TimedRotatingFileHandler(
        filename=_getenv('LOG_FILE', 'logs/houston.log'),
        when='midnight',
        backupCount=int(_getenv('LOG_FILE_BACKUP_COUNT', 30)),
    ),
]


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
    if _getenv('TERM', None) is None:
        try:
            log_width = _getenv('LOG_WIDTH', None)
            log_width = float(log_width)
        except Exception:
            log_width = 200

        # Inside docker without TTL
        console_kwargs['force_terminal'] = True
        console_kwargs['force_interactive'] = True
        console_kwargs['width'] = log_width
        console_kwargs['soft_wrap'] = True

    rich.reconfigure(**console_kwargs)
    handlers.append(RichHandler(**handler_kwargs))
except ImportError:  # pragma: no cover
    print('Unable to load Rich for logging')

logging.basicConfig(handlers=handlers, **logging_config)
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
            'shell': '/bin/sh' if platform.system() != 'Windows' else _getenv('COMSPEC'),
        },
        'root_namespace': namespace,
        'invoke_execute': invoke_execute,
    }
)
