# -*- coding: utf-8 -*-
import app.extensions.logging as AuditLog
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
    from app.modules.notifications.models import NotificationType

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

    # validate_merge_request should check hashes etc and means we are good to merge
    target_individual = all_individuals.pop(0)
    # TODO additional work TBD regarding conflict args/parameters (DEX-514)
    try:
        res = target_individual.merge_from(*all_individuals)
    except Exception as ex:
        res = f'Exception caught: {str(ex)}'
    if not isinstance(res, dict):
        msg = f'{log_id} (via celery task) merge_from failed: {res}'
        AuditLog.backend_fault(log, msg)
        return

    log.info(f'{log_id} merge completed, results={res}')

    # notify users that merge has happened
    #   NOTE request_data here may need some altering depending on what final templates look like
    #   also unclear who *sender* will be, so that may need to be passed
    request_data = {
        'id': self.request.id,
        'from_individual_ids': from_individual_ids,
    }
    Individual.merge_request_notify(
        [target_individual], request_data, NotificationType.individual_merge_complete
    )
