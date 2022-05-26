# -*- coding: utf-8 -*-
import logging

from flask import current_app

from app.extensions.celery import celery

SAGE_SYNC_FREQUENCY = 60 * 60


log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def sage_task_setup_periodic_tasks(sender, **kwargs):
    if SAGE_SYNC_FREQUENCY is not None:
        sender.add_periodic_task(
            SAGE_SYNC_FREQUENCY,
            sage_task_sync.s(),
            name='Sync and Prune Sage',
        )


@celery.task
def sage_task_sync():
    from app.modules.annotations.models import Annotation
    from app.modules.assets.models import Asset

    # Sync all Assets
    Asset.sync_all_with_sage(ensure=True, prune=True)

    # Sync all Annotations
    Annotation.sync_all_with_sage(ensure=True, prune=True)

    # Sync all job results
    current_app.sage.sync_jobs()

    # Get status of Sage
    current_app.sage.get_status()
