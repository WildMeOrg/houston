# -*- coding: utf-8 -*-
import logging

from app.extensions.celery import celery

PROMETHEUS_UPDATE_FREQUENCY = 60 * 10


log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def prometheus_task_setup_periodic_tasks(sender, **kwargs):
    if PROMETHEUS_UPDATE_FREQUENCY is not None:
        sender.add_periodic_task(
            PROMETHEUS_UPDATE_FREQUENCY,
            prometheus_update.s(),
            name='Update Prometheus',
        )


@celery.task
def prometheus_update():
    import json

    from app.extensions import prometheus

    samples = prometheus.update()

    data = json.dumps(samples)
    response = prometheus.send_update(data)

    assert response is not None
    assert response.status_code == 200
