# -*- coding: utf-8 -*-
import logging
from app.extensions.celery import celery

log = logging.getLogger(__name__)


@celery.task(
    bind=True,
    # autoretry_for=(requests.exceptions.RequestException,),
    # default_retry_delay=3,
    # max_retries=10,
)
def execute_merge_request(self, target_individual_guid, from_individual_ids, parameters):
    from .models import Individual

    Individual.merge_request_celery_task(
        self, target_individual_guid, from_individual_ids, parameters
    )
