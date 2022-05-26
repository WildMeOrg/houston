# -*- coding: utf-8 -*-
import logging

from app.extensions.celery import celery

log = logging.getLogger(__name__)

# JOB_CONTROL_CHECK_FREQUENCY = 120
JOB_CONTROL_CHECK_FREQUENCY = None


@celery.on_after_configure.connect
def job_control_task_setup_periodic_tasks(sender, **kwargs):
    if JOB_CONTROL_CHECK_FREQUENCY is not None:
        sender.add_periodic_task(
            JOB_CONTROL_CHECK_FREQUENCY,
            check_jobs.s(),
            name='Job Control Checking',
        )


@celery.task
def check_jobs():
    from .models import JobControl

    JobControl.check_jobs()
