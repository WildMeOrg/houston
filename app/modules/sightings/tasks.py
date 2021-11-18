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
def send_identification(
    sighting_guid, config_id, algorithm_id, annotation_uuid, annotation_sage_guid
):
    from .models import Sighting

    sighting = Sighting.query.get(sighting_guid)

    if sighting:
        sighting.send_identification(
            config_id, algorithm_id, annotation_uuid, annotation_sage_guid
        )
    else:
        log.warning('Failed to find the sighting to perform Identification on')
