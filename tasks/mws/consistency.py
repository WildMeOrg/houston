# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"""
This file contains initialization data for development usage only.

You can execute this code via ``invoke mws.consistency``
"""
import logging
from tasks.utils import app_context_task

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


@app_context_task
def all(context, skip_on_failure=False):
    log.info('Initializing consistency checks...')

    try:
        pass
    except AssertionError as exception:
        if not skip_on_failure:
            log.exception('Consistency checks failed.')
        else:
            log.debug(
                'The following error was ignored due to the `skip_on_failure` flag: %s',
                exception,
            )
            log.info('Running consistency checks is skipped.')
    else:
        log.info('Consistency checks successfully applied.')
