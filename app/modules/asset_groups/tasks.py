# -*- coding: utf-8 -*-
import logging

import requests.exceptions
import sqlalchemy
from flask import current_app

import app.extensions.logging as AuditLog
from app.extensions.celery import celery

log = logging.getLogger(__name__)


@celery.task(
    autoretry_for=(requests.exceptions.RequestException, sqlalchemy.exc.SQLAlchemyError),
    default_retry_delay=10,
    max_retries=10,
)
def sage_detection(asset_group_sighting_guid, model):
    from .models import AssetGroupSighting

    asset_group_sighting = AssetGroupSighting.query.get(asset_group_sighting_guid)
    if asset_group_sighting:
        log.debug(f'Celery running sage detection for {asset_group_sighting_guid}')
        asset_group_sighting.send_detection_to_sage(model)


@celery.task
def fetch_sage_detection_result(asset_group_sighting_guid, job_id):
    from .models import AssetGroupSighting

    asset_group_sighting = AssetGroupSighting.query.get(asset_group_sighting_guid)
    if asset_group_sighting:
        try:
            response = current_app.sage.request_passthrough_result(
                'engine.result',
                'get',
                target='default',
                args=job_id,
            )
        except Exception:
            message = f'Failed to fetch the Sage detection result for AGS {asset_group_sighting.guid} with job_id {job_id}'
            AuditLog.audit_log_object_warning(log, asset_group_sighting, message)
            log.warning(message)
            return
        asset_group_sighting.detected(job_id, response)
    else:
        log.warning(
            f'Failed to find the asset Group Sighting {asset_group_sighting_guid}'
        )
