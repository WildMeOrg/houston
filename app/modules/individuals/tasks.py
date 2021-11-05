# -*- coding: utf-8 -*-
import logging

# import requests.exceptions
from app.extensions.celery import celery
from datetime import datetime


log = logging.getLogger(__name__)


@celery.task(
    # autoretry_for=(requests.exceptions.RequestException,),
    # default_retry_delay=3,
    # max_retries=10,
)
def init_merge_request(target_individual_guid, from_individual_ids, parameters):
    # from .models import Individual
    msg = f'******** MERGE_REQUEST_TIMER on {target_individual_guid}/{from_individual_ids}/{parameters}:  {datetime.utcnow()} ********'
    log.warning(msg)
    f = open('/tmp/init_merge_request.log', 'a')
    f.write(msg + '\n')
    f.close()
