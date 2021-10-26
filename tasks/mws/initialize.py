# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""
This file contains initialization tasks to synchronize data from the EDM

You can execute this code via ``invoke mws.initialize``
"""
import logging

from tasks.utils import app_context_task

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


@app_context_task
def all(context, edm_authentication=None, skip_on_failure=False):
    log.info('Initializing tasks...')

    try:
        pass
    except AssertionError as exception:
        if not skip_on_failure:
            log.error('%s', exception)
        else:
            log.debug(
                'The following error was ignored due to the `skip_on_failure` flag: %s',
                exception,
            )
            log.info('Running initialize tasks is skipped.')
    else:
        log.info('Initialize tasks successfully applied.')
