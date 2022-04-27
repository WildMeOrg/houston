# -*- coding: utf-8 -*-
import logging

import requests.exceptions

from app.extensions.celery import celery

log = logging.getLogger(__name__)


# RequestException is a base class for all sorts of errors, inc timeouts so this handles them all
@celery.task(
    autoretry_for=(requests.exceptions.RequestException,),
    default_retry_delay=600,
    max_retries=10,
)
def send_identification(
    sighting_guid,
    config_id,
    algorithm_id,
    annotation_uuid,
    annotation_sage_guid,
    matching_set_query=None,
):
    from .models import Sighting

    sighting = Sighting.query.get(sighting_guid)

    if sighting:
        sighting.send_identification(
            config_id,
            algorithm_id,
            annotation_uuid,
            annotation_sage_guid,
            matching_set_query,
        )
    else:
        log.warning(
            f'Failed to find the sighting {sighting_guid} to perform Identification on'
        )


# RequestException is a base class for all sorts of errors, inc timeouts so this handles them all
@celery.task(
    autoretry_for=(requests.exceptions.RequestException,),
    default_retry_delay=600,
    max_retries=10,
)
# as for the above but this time for everything in the sighting
def send_all_identification(sighting_guid):
    from .models import Sighting

    sighting = Sighting.query.get(sighting_guid)
    if sighting:
        sighting.send_all_identification()
    else:
        log.warning(
            f'Failed to find the sighting {sighting_guid} to perform Identification on'
        )
