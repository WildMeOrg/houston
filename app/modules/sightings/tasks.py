# -*- coding: utf-8 -*-
import logging

from flask import current_app

import app.extensions.logging as AuditLog
from app.extensions.celery import celery

log = logging.getLogger(__name__)


@celery.task
def send_identification(
    sighting_guid,
    annotation_guid,
    config_id,
    algorithm_id,
    matching_set_query=None,
):
    from app.modules.annotations.models import Annotation
    from app.modules.sightings.models import Sighting

    sighting = Sighting.query.get(sighting_guid)
    annotation = Annotation.query.get(annotation_guid)

    if sighting is not None and annotation is not None:
        sighting.send_identification(
            annotation,
            config_id,
            algorithm_id,
            matching_set_query,
        )
    else:
        if sighting is None:
            log.warning(
                f'Failed to find the sighting {sighting_guid} to perform Identification on'
            )
        if annotation is None:
            log.warning(
                f'Failed to find the annotation {annotation_guid} to perform Identification on'
            )


@celery.task
# as for the above but this time for everything in the sighting
def send_all_identification(sighting_guid):
    from app.modules.sightings.models import Sighting

    sighting = Sighting.query.get(sighting_guid)
    if sighting:
        sighting.send_all_identification()
    else:
        log.warning(
            f'Failed to find the sighting {sighting_guid} to perform Identification on'
        )


@celery.task
def fetch_sage_identification_result(sighting_guid, job_id):
    from app.modules.sightings.models import Sighting

    sighting = Sighting.query.get(sighting_guid)
    if sighting:
        try:
            response = current_app.sage.request_passthrough_result(
                'engine.result',
                'get',
                target='default',
                args=job_id,
            )
        except Exception:
            message = f'Failed to fetch the Sage identification result  for sighting {sighting_guid} with job_id {job_id}'
            AuditLog.audit_log_object_fault(log, sighting, message)
            log.warning(message)
            return
        sighting.identified(job_id, response)
    else:
        log.warning(f'Failed to find the sighting {sighting_guid}')
