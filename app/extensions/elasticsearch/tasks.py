# -*- coding: utf-8 -*-
import logging

import uuid
from flask import current_app
from app.extensions.celery import celery
from app.extensions import elasticsearch as es
from app.extensions import db
from datetime import timedelta

import tqdm


log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def elasticsearch_setup_periodic_tasks(sender, **kwargs):
    try:
        update_freq = int(current_app.config['ELASTICSEARCH_UPDATE_FREQUENCY'])
        assert update_freq >= 1
    except Exception:
        update_freq = None

    try:
        firewall_freq = int(current_app.config['ELASTICSEARCH_FIREWALL_FREQUENCY'])
        assert firewall_freq >= 1
    except Exception:
        firewall_freq = None

    if update_freq is not None:
        sender.add_periodic_task(
            update_freq,
            elasticsearch_refresh_index_all.s(),
            name='Refresh Elasticsearch',
        )

    if firewall_freq is not None:
        sender.add_periodic_task(
            firewall_freq,
            elasticsearch_invalidate_indexed_timestamps.s(),
            name='Clear Elasticsearch Indexed Timestamps',
        )


@celery.task
def elasticsearch_refresh_index_all():
    log.info('Running Refresh Index All (testing = %r)' % (current_app.testing,))
    if current_app.testing:
        log.info('...skipping')
        return True

    # Re-index everything
    with es.session.begin(blocking=True):
        es.init_elasticsearch_index(app=current_app, verbose=False)

    # Check on the status of the DB relative to ES
    status = es.es_status(app=current_app)
    log.info('Elasticsearch status = %r' % (status,))

    # Ignore any active jobs
    status.pop('active', None)
    return len(status) == 0


@celery.task
def elasticsearch_invalidate_indexed_timestamps():
    log.info(
        'Running Invalidate Indexed Timestamps (testing = %r)' % (current_app.testing,)
    )
    if current_app.testing:
        log.info('...skipping')
        return True

    delta = timedelta(seconds=1)
    with es.session.begin(disabled=True):
        for cls in es.REGISTERED_MODELS:
            log.info('Invalidating %r' % (cls,))
            with db.session.begin():
                objs = cls.query.all()
                if len(objs) > 0:
                    desc = 'Invalidating (Bulk) %s' % (cls.__name__,)
                    for obj in tqdm.tqdm(objs, desc=desc):
                        obj.indexed = obj.updated - delta

    return True


@celery.task
def elasticsearch_index_bulk(index, items):
    app = current_app
    cls = es.get_elasticsearch_cls_from_index(index)

    log.info(
        'Restoring %d index objects for cls = %r, index = %r'
        % (
            len(items),
            cls,
            index,
        )
    )

    succeeded, total = 0, len(items)
    if cls is not None:
        restored_items = []
        for guid, force in items:
            guid_ = uuid.UUID(guid)
            obj = cls.query.get(guid_)
            if obj is not None:
                item = (obj, force)
                restored_items.append(item)

        total = len(restored_items)
        succeeded = es.session._es_index_bulk(cls, restored_items, app=app)

    if succeeded < total:
        log.warning(
            'Bulk index had %d successful items out of %d'
            % (
                succeeded,
                total,
            )
        )

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

    succeeded, total = 0, len(guids)
    if cls is not None:
        succeeded = es.session._es_delete_guid_bulk(cls, guids, app=app)

    if succeeded < total:
        log.warning(
            'Bulk delete had %d successful items out of %d'
            % (
                succeeded,
                total,
            )
        )

    return succeeded == total
