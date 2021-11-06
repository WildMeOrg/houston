# -*- coding: utf-8 -*-
import app.extensions.logging as AuditLog
import logging

# import requests.exceptions
from app.extensions.celery import celery
from datetime import datetime


log = logging.getLogger(__name__)


@celery.task(
    bind=True,
    # autoretry_for=(requests.exceptions.RequestException,),
    # default_retry_delay=3,
    # max_retries=10,
)
def execute_merge_request(self, target_individual_guid, from_individual_ids, parameters):
    from .models import Individual

    log_id = f'<execute_merge_request {self.request.id}>'
    log.info(
        f'{log_id} initiated for Individual {target_individual_guid} (from {from_individual_ids}; {parameters})'
    )
    all_individuals = Individual.validate_merge_request(
        target_individual_guid, from_individual_ids, parameters
    )
    if not all_individuals:
        msg = f'{log_id} failed validation'
        AuditLog.backend_fault(log, msg)
        return

    msg = f'******** MERGE_REQUEST_TIMER on {target_individual_guid}/{from_individual_ids}/{parameters}:  {datetime.utcnow()} ********'
    log.warning(msg)
    f = open('/tmp/init_merge_request.log', 'a')
    f.write(msg + '\n')
    f.close()
