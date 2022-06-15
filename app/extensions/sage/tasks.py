# -*- coding: utf-8 -*-
import logging

from flask import current_app

from app.extensions.celery import celery

SAGE_DATA_SYNC_FREQUENCY = None  # 60 * 60
SAGE_JOBS_SYNC_FREQUENCY = 60 * 5


log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def sage_task_setup_periodic_tasks(sender, **kwargs):
    if SAGE_DATA_SYNC_FREQUENCY is not None:
        sender.add_periodic_task(
            SAGE_DATA_SYNC_FREQUENCY,
            sage_task_data_sync.s(),
            name='Sync and Prune Sage Data',
        )
    if SAGE_JOBS_SYNC_FREQUENCY is not None:
        sender.add_periodic_task(
            SAGE_JOBS_SYNC_FREQUENCY,
            sage_task_jobs_sync.s(),
            name='Sync and Fetch Sage Jobs',
        )


@celery.task
def sage_task_data_sync():
    from app.modules.annotations.models import Annotation
    from app.modules.assets.models import Asset

    # Sync all Assets
    Asset.sync_all_with_sage(ensure=True)

    # Sync all Annotations
    Annotation.sync_all_with_sage(ensure=True)

    # Get status of Sage
    current_app.sage.get_status()


@celery.task
def sage_task_jobs_sync():
    # Sync all job results
    current_app.sage.sync_jobs()
