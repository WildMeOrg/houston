# -*- coding: utf-8 -*-
import logging

import requests.exceptions
import sqlalchemy

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
