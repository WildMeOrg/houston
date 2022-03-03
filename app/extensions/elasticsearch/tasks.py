# -*- coding: utf-8 -*-
import logging

import uuid
from flask import current_app
from app.extensions.celery import celery
from app.extensions import elasticsearch as es


log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def elasticsearch_setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        60, elasticsearch_refresh_index_all.s(), name='Refresh Elasticsearch'
    )


@celery.task
def elasticsearch_refresh_index_all():
    # Re-index everything
    with es.session.begin(blocking=True):
        es.init_elasticsearch_index(app=current_app, verbose=False, pit=False)

    # Check on the status of the DB relative to ES
    status = es.es_status(app=current_app)
    log.info('Elasticsearch status = %r' % (status,))

    # Ignore any active jobs
    status.pop('active', None)
    return len(status) == 0


@celery.task
def elasticsearch_index_bulk(index, guids):
    app = current_app
    cls = es.get_elasticsearch_cls_from_index(index)

    log.info(
        'Restoring %d index objects for cls = %r, index = %r'
        % (
            len(guids),
            cls,
            index,
        )
    )

    succeeded, total = -1, 0
    if cls is not None:
        objs = []
        for guid in guids:
            guid_ = uuid.UUID(guid)
            obj = cls.query.get(guid_)
            if obj is not None:
                objs.append(obj)

        total = len(objs)
        succeeded = es.session._es_index_bulk(cls, objs, app=app)

    return succeeded == total


@celery.task
def elasticsearch_delete_guid_bulk(index, guids):
    app = current_app
    cls = es.get_elasticsearch_cls_from_index(index)

    log.info(
        'Deleting %d items for cls = %r, index = %r'
        % (
            len(guids),
            cls,
            index,
        )
    )

    succeeded, total = -1, 0
    if cls is not None:
        total = len(guids)
        succeeded = es.session._es_delete_guid_bulk(cls, guids, app=app)

    return succeeded == total
