# -*- coding: utf-8 -*-
import logging

from app.extensions.celery import celery


TUS_CLEANUP_FREQUENCY = 60 * 15


log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def tus_task_setup_periodic_tasks(sender, **kwargs):
    if TUS_CLEANUP_FREQUENCY is not None:
        sender.add_periodic_task(
            TUS_CLEANUP_FREQUENCY,
            tus_task_cleanup.s(),
            name='Clean-up Tus Uploads Directory',
        )


@celery.task
def tus_task_cleanup():
    from app.extensions import tus

    return tus.tus_cleanup()
