# -*- coding: utf-8 -*-
import logging

import requests.exceptions

from app.extensions.celery import celery


log = logging.getLogger(__name__)


@celery.task(
    autoretry_for=(requests.exceptions.RequestException,),
    default_retry_delay=600,
    max_retries=10,
)
def send_mws_backend_operation(mission_guid):
    from .models import Mission

    mission = Mission.query.get(mission_guid)

    if mission:
        mission.send_mws_backend_operation()
    else:
        log.warning('Failed to find the mission to perform MWS operation')
