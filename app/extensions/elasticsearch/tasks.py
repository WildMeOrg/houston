# -*- coding: utf-8 -*-
import logging

import uuid
from app.extensions.celery import celery


ELASTICSEARCH_UPDATE_FREQUENCY = 60
ELASTICSEARCH_MAXIMUM_SESSION_LENGTH = ELASTICSEARCH_UPDATE_FREQUENCY * 1
ELASTICSEARCH_FIREWALL_FREQUENCY = ELASTICSEARCH_UPDATE_FREQUENCY * 10


log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def elasticsearch_setup_periodic_tasks(sender, **kwargs):
    if ELASTICSEARCH_UPDATE_FREQUENCY is not None:
        sender.add_periodic_task(
            ELASTICSEARCH_UPDATE_FREQUENCY,
            elasticsearch_refresh_index_all.s(),
            name='Refresh Elasticsearch',
        )

    if ELASTICSEARCH_FIREWALL_FREQUENCY is not None:
        sender.add_periodic_task(
            ELASTICSEARCH_FIREWALL_FREQUENCY,
            elasticsearch_invalidate_indexed_timestamps.s(),
            name='Clear Elasticsearch Indexed Timestamps',
        )


@celery.task
def elasticsearch_refresh_index_all(force=False):
    from app.extensions import elasticsearch as es
    from flask import current_app

    testing = current_app.testing and not force
    log.info('Running Refresh Index All (testing = %r)' % (testing,))
    if testing:
        log.info('...skipping')
        return True

    # Check if we have been in a session block too long
    es.session.check(ELASTICSEARCH_MAXIMUM_SESSION_LENGTH)

    # Re-index everything
    try:
        with es.session.begin(blocking=True, verify=True):
            es.es_index_all(app=current_app)
    except Exception:
        log.info('Elasticsearch Index All session failed to verify')

    # Check on the status of the DB relative to ES
    status = es.es_status(app=current_app)
    log.info('Elasticsearch status = %r' % (status,))

    # Ignore any active jobs
    status.pop('active', None)
    return len(status) == 0


@celery.task
def elasticsearch_invalidate_indexed_timestamps(force=False):
    from app.extensions import elasticsearch as es
    from app.extensions import db
    from flask import current_app

    testing = current_app.testing and not force
    log.info('Running Invalidate Indexed Timestamps (testing = %r)' % (testing,))
    if testing:
        log.info('...skipping')
        return True

    with es.session.begin(disabled=True):
        for cls in es.REGISTERED_MODELS:
            with db.session.begin():
                cls.invalidate_all()

    return True


@celery.task
def elasticsearch_index_bulk(index, items):
    from app.extensions import elasticsearch as es
    from flask import current_app

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

    all_guids = cls.query.with_entities(cls.guid).all()

    succeeded, total = 0, len(items)
    if cls is not None:
        restored_items = []
        missing_items = []
        for item in items:
            guid, force = item
            guid_ = uuid.UUID(guid)
            obj = cls.query.get(guid_)
            if obj is not None:
                item = (obj, force)
                restored_items.append(item)
            else:
                missing_items.append(item)

        if len(missing_items) > 0:
            log.warning(
                'Missing %d restored items for %r (index = %r, app.testing = %r, %d items in DB)'
                % (
                    len(missing_items),
                    cls,
                    index,
                    app.testing,
                    len(all_guids),
                )
            )

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
    from app.extensions import elasticsearch as es
    from flask import current_app

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
