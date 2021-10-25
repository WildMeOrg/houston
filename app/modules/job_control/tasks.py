# -*- coding: utf-8 -*-
import logging
from app.extensions.celery import celery

log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(120.0, check_jobs.s(), name='Job Control Checking')


@celery.task
def check_jobs():
    from .models import JobControl

    JobControl.check_jobs()
