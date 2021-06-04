# -*- coding: utf-8 -*-
import logging

from .models import JobControl

from app.extensions.celery import celery

log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(10.0, JobControl.periodic.s(), name='Job Control background')
