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
def send_identification(sighting_guid, matching_data_set, model, annotation_uuid):
    from .models import Sighting

    sighting = Sighting.query.get(sighting_guid)

    if sighting:
        sighting.send_identification(matching_data_set, model, annotation_uuid)
