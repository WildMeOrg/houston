# -*- coding: utf-8 -*-
""" Client initialization for Elasticsearch """
import datetime
import enum
import json
import logging
import pprint
import sys
import time
import types
import uuid
import weakref

import elasticsearch
import flask_sqlalchemy
import sqlalchemy
import sqlalchemy_utils
import tqdm
import utool as ut
import werkzeug
from elasticsearch import helpers
from sqlalchemy.inspection import inspect

from app.extensions import db, executor, is_extension_enabled
from app.extensions.api import api_v1
from app.utils import HoustonException

if not is_extension_enabled('elasticsearch'):
    raise RuntimeError('Elastic Search is not enabled')

ENABLED = True
TESTING_PREFIX = 'testing'
REGISTERED_MODELS = {}

CELERY_VERIFY_TIMEOUT = 60.0
CELERY_ASYNC_PROMISES = []

ELASTICSEARCH_SORTING_PREFIX = 'elasticsearch.'

MAX_UNICODE_CODE_POINT_CHAR = chr(int(hex(sys.maxunicode), 16))

log = logging.getLogger('elasticsearch')  # pylint: disable=invalid-name

# Global object session
session = None

ELASTICSEARCH_VERBOSE = False


class ElasticsearchModel(object):
    """Adds `viewed` column to a derived declarative model."""

    @classmethod
    def get_elasticsearch_schema(cls):
        return None

    @classmethod
    def get_elasticsearch_settings(cls):
        settings = {
            'analysis': {
                'normalizer': {
                    'codex_keyword_normalizer': {
                        'type': 'custom',
                        'char_filter': [],
                        'filter': ['lowercase', 'asciifolding'],
                    }
                }
            }
        }
        return settings

    @classmethod
    def patch_elasticsearch_mappings(cls, mappings):
        # Check all fields that are GUIDs or "IDs"
        for key in mappings:
            # Ensure all GUIDs and the _schema
            if (
                key in ['guid', '_schema', 'email']
                or key.endswith('_guid')
                or key.endswith('_id')
                or key.endswith('_keyword')
                or key.endswith('ID')
                or key.endswith('Id')
            ):
                mappings[key] = {
                    'type': 'keyword',
                }
            # # Convert all text types to keywords by default
            # if mappings[key].get('type', None) in ['text']:
            #     mappings[key] = {
            #         'type': 'keyword',
            #     }
            value = mappings.get(key, {})
            if isinstance(value, dict):
                # Recursively catch all properties of a field as well
                for subkey in value:
                    if subkey in ['properties']:
                        mappings[key][subkey] = cls.patch_elasticsearch_mappings(
                            mappings[key][subkey]
                        )

        return mappings

    @classmethod
    def index_hook_cls(cls, *args, **kwargs):
        pass

    @classmethod
    def pit(cls, *args, **kwargs):
        return es_pit(cls, *args, **kwargs)

    @classmethod
    def _index(cls):
        return es_index_name(cls)

    @classmethod
    def index_all(cls, app=None, prune=True, pit=False, update=True, force=False):
        index = cls._index()

        es_index_mappings_patch(cls, app=app)

        session_forced = session.in_forced_mode()

        if index is None:
            return

        with session.begin():
            # If pruning, delete anything from the index that is not in the database
            indexed_guids = set(
                cls.elasticsearch(search={}, app=app, load=False, prune=prune)
            )

            if pit:
                # Establish a new point-in-time
                cls.pit(app=app)

            if update:
                all_guids = cls.query.with_entities(cls.guid).all()
                all_guids = {item[0] for item in all_guids}

                missing_guids = all_guids - indexed_guids

                # If not forcing, only update the items that are outdated
                if force:
                    outdated_guids = all_guids
                else:
                    outdated_guids = (
                        cls.query.filter(cls.updated > cls.indexed)
                        .with_entities(cls.guid)
                        .all()
                    )
                    outdated_guids = {item[0] for item in outdated_guids}

                guids = list(missing_guids | outdated_guids)
                force_str = ' (by session)' if not force and session_forced else ''
                if session_forced:
                    force = True

                if ELASTICSEARCH_VERBOSE:
                    log.info(
                        'Elasticsearch Index All %r into %r (%d items, force=%r%s)'
                        % (
                            cls,
                            index,
                            len(guids),
                            force,
                            force_str,
                        )
                    )

                # Re-index all objects in our local database
                desc_action = 'Tracking' if session.in_bulk_mode() else 'Indexing'
                desc = '{} {}'.format(
                    desc_action,
                    cls.__name__,
                )
                quiet = len(guids) < 100

                # Load all objects and index
                objs = cls.query.filter(cls.guid.in_(guids)).order_by(cls.guid).all()
                for obj in tqdm.tqdm(objs, desc=desc, disable=quiet):
                    obj.index(app=app, force=force)

    @classmethod
    def prune_all(cls, app=None):
        index = cls._index()

        if index is None:
            return

        with session.begin():
            guids = cls.query.with_entities(cls.guid).all()
            guids = list({item[0] for item in guids})

            if ELASTICSEARCH_VERBOSE:
                log.info(
                    'Pruning Index All %r from %r (%d items)'
                    % (
                        cls,
                        index,
                        len(guids),
                    )
                )

            # Prune all objects in our local database
            desc = 'Pruning {}'.format(cls.__name__)
            quiet = len(guids) < 100
            for guid in tqdm.tqdm(guids, desc=desc, disable=quiet):
                es_delete_guid(cls, guid, app=app)

    @classmethod
    def invalidate_all(cls, app=None):
        if ELASTICSEARCH_VERBOSE:
            log.info('Invalidating {!r}'.format(cls))
        with db.session.begin(subtransactions=True):
            db.session.execute(
                cls.bulk_class()
                .__table__.update()
                .values(updated=datetime.datetime.utcnow())
            )
        objs = cls.query.all()

        if len(objs) > 0:
            for obj in objs:
                assert not obj.elasticsearchable

    @classmethod
    def elasticsearch(cls, search, app=None, total=False, *args, **kwargs):
        body = {}

        if search is None:
            search = {}

        if len(search) > 0:
            body['query'] = search

        if total:
            kwargs['total'] = True

        with session.begin():
            response = es_elasticsearch(app, cls, body, *args, **kwargs)

        return response

    @classmethod
    def bulk_class(cls):
        from app.extensions.git_store import GitStore

        bulk_cls = GitStore if issubclass(cls, GitStore) else cls
        return bulk_cls

    @property
    def index_name(self):
        return self.__class__._index()

    @property
    def elasticsearchable(self):
        return self.indexed >= self.updated

    def index_hook_obj(self, *args, **kwargs):
        return self.__class__.index_hook_cls(*args, **kwargs)

    def available(self, *args, **kwargs):
        return es_exists(self, *args, **kwargs)

    def invalidate(self, *args, **kwargs):
        return es_invalidate(self, *args, **kwargs)

    def validate(self, *args, **kwargs):
        return es_validate(self, *args, **kwargs)

    def serialize(self, *args, **kwargs):
        return es_serialize(self, *args, **kwargs)

    def index(self, *args, **kwargs):
        return es_index(self, *args, **kwargs)

    def fetch(self, *args, **kwargs):
        return es_get(self, *args, **kwargs)

    def prune(self, *args, **kwargs):
        return es_delete(self, *args, **kwargs)


class ElasticSearchBulkOperation(object):
    def __init__(self, app=None, blocking=None):
        self.app = app
        self.config = {}

        if blocking is None:
            blocking = app.config.get('ELASTICSEARCH_BLOCKING', False)
        self.blocking = blocking

        self.reset()

    def in_bulk_mode(self):
        return len(self.depth) > 0

    def in_skip_mode(self):
        return self.in_bulk_mode() and self.depth[0] is None

    def in_forced_mode(self):
        forced = False
        if self.in_bulk_mode():
            top_config = self.depth[0]
            if top_config is not None:
                forced = top_config.get('forced', top_config.get('force', False))
        return forced

    def track_bulk_action(self, action, item, force=False):
        if self.in_forced_mode():
            force = True

        if ELASTICSEARCH_VERBOSE:
            log.debug(
                'Tracking %r action for %r (force = %r)'
                % (
                    action,
                    item,
                    force,
                )
            )

        if is_disabled():
            if ELASTICSEARCH_VERBOSE:
                log.debug('...disabled')
            return 'disabled'

        if self.in_skip_mode():
            if ELASTICSEARCH_VERBOSE:
                log.debug('...skipped')
            return 'skipped'

        action = action.lower().strip()

        if action == 'index':
            cls = item.__class__
            item = (item, force)
        elif action == 'delete':
            cls, guid = item
            item = str(guid)
        else:  # pragma: no cover
            raise RuntimeError()

        if cls not in self.bulk_actions:
            self.bulk_actions[cls] = {}
        if action not in self.bulk_actions[cls]:
            self.bulk_actions[cls][action] = []

        self.bulk_actions[cls][action].append(item)
        if ELASTICSEARCH_VERBOSE:
            log.debug('...tracked')

        return 'tracked'

    def begin(self, **kwargs):
        self.config = kwargs
        return self

    def reset(self):
        self.timestamp = datetime.datetime.utcnow()
        self.depth = []
        self.bulk_actions = {}

    def _es_exists_bulk(self, cls, guids, app=None):
        exists = set()

        if app is None:
            app = self.app

        index = es_index_name(cls, app=app)

        if index is None:
            return exists

        actions = []
        for guid in guids:
            id_ = str(guid)
            action = {
                '_id': id_,
                '_op_type': 'create',
            }
            actions.append(action)

        all_guids = set(map(str, guids))
        try:
            responses = list(
                helpers.parallel_bulk(
                    app.es, actions, index=index, chunk_size=10000, raise_on_error=False
                )
            )
            for success, response in responses:
                create = response.get('create', {})
                flag = 'document already exists' in create.get('error', {}).get(
                    'reason', ''
                )
                if flag:
                    guid = create.get('_id', None)
                    if guid in all_guids:
                        exists.add(guid)
        except (
            AssertionError,
            helpers.errors.BulkIndexError,
            elasticsearch.exceptions.ElasticsearchException,
        ):  # pragma: no cover
            pass

        return exists

    def _es_index_bulk(self, cls, items, app=None, level=0, parallel=False):
        if app is None:
            app = self.app

        index = es_index_name(cls, app=app)

        if index is None:
            return 0

        outdated = []
        forced = []
        skipped = []
        for item in items:
            obj, force = item
            if not obj.elasticsearchable:
                outdated.append(obj)
            elif force:
                forced.append(obj)
            else:
                skipped.append(obj)

        if ELASTICSEARCH_VERBOSE:
            log.info(
                'Indexing (Bulk) %r into %r (%d items: %d outdated, %d forced, %d skipped)'
                % (
                    cls,
                    index,
                    len(items),
                    len(outdated),
                    len(forced),
                    len(skipped),
                )
            )

        pending = outdated + forced

        if len(pending) == 0:
            return len(skipped)

        # Check schema mappings first
        es_index_mappings_patch(cls, app=app)

        # Continue to serialize and send
        level_str = '' if level == 0 else ' [retry=%d]' % (level,)
        desc = 'Serializing (Bulk) {}{}'.format(
            cls.__name__,
            level_str,
        )

        datas = None
        if parallel:
            try:
                datas = es_serialize_parallel(pending, desc, app=app)
            except Exception:
                datas = None

        if datas is None:
            # Compute datas in serial
            datas = []
            for obj in tqdm.tqdm(pending, desc=desc):
                data = obj.serialize()
                datas.append(data)

        actions = []
        for obj, data in zip(pending, datas):
            index_, id_, body = data
            assert index == index_
            action = body
            action['_id'] = str(id_)
            actions.append(action)

        try:
            responses = list(
                helpers.parallel_bulk(
                    app.es, actions, index=index, chunk_size=1000, raise_on_error=False
                )
            )
            total = 0
            errors = []
            for success, response in responses:
                if success:
                    total += 1
                else:
                    errors.append(response)

            if errors:
                log.error(f'Bulk ES index errors: {errors}')
            assert total == len(actions)
            assert len(errors) == 0
        except (
            AssertionError,
            helpers.errors.BulkIndexError,
            elasticsearch.exceptions.ElasticsearchException,
        ):  # pragma: no cover
            if len(items) == 1:
                obj, force = items[0]
                return obj.elasticsearchable

            total = 0
            new_level = level + 1
            chunk_size = max(1, len(items) // 2)
            chunks = list(ut.ichunks(items, chunk_size))
            for chunk in chunks:
                success = self._es_index_bulk(
                    cls, chunk, app=app, level=new_level, parallel=parallel
                )
                total += success

            if level == 0:
                failed = len(items) - total
                if failed > 0:
                    log.error('Bulk ES index failed for %d items' % (failed,))

            return total

        # We only update the indexed timestamps of the objects that succeded as a group
        pending_guids = [item.guid for item in pending]
        with db.session.begin(subtransactions=True):
            db.session.execute(
                cls.bulk_class()
                .__table__.update()
                .values(indexed=datetime.datetime.utcnow())
                .where(cls.bulk_class().guid.in_(pending_guids))
            )

        # Refresh the index
        es_refresh_index(index, app=app)

        total = len(actions) + len(skipped)
        return total

    def _es_delete_guid_bulk(self, cls, guids, app=None, level=0):
        if app is None:
            app = self.app

        index = es_index_name(cls, app=app)

        if index is None:
            return 0

        exists = self._es_exists_bulk(cls, guids, app=app)

        pending = []
        skipped = []
        for guid in guids:
            if str(guid) in exists:
                pending.append(guid)
            else:
                skipped.append(guid)

        if len(pending) == 0:
            return len(skipped)

        actions = []
        for guid in pending:
            action = {
                '_id': str(guid),
                '_op_type': 'delete',
            }
            actions.append(action)

        level_str = '' if level == 0 else ' [retry=%d]' % (level,)
        log.info(
            'Deleting (Bulk) %r into %r (%d guids: %d actions, %d skipped)%s'
            % (
                cls,
                index,
                len(guids),
                len(actions),
                len(skipped),
                level_str,
            )
        )

        try:
            responses = list(
                helpers.parallel_bulk(
                    app.es, actions, index=index, chunk_size=10000, raise_on_error=False
                )
            )
            total = 0
            errors = []
            for success, response in responses:
                if success:
                    total += 1
                else:
                    errors.append(response)

            assert total == len(actions)
            assert len(errors) == 0
        except (
            AssertionError,
            helpers.errors.BulkIndexError,
            elasticsearch.exceptions.ElasticsearchException,
        ):  # pragma: no cover
            if len(guids) == 1:
                # Base case, check if the one ID exists
                guid = guids[0]
                id_ = str(guid)
                exists = app.es.exists(index, id=id_)
                return 0 if exists else 1

            # Recursive case, retry the list we just got, splitting it into two pieces
            total = 0
            new_level = level + 1
            chunk_size = max(1, len(guids) // 2)
            chunks = list(ut.ichunks(guids, chunk_size))
            for chunk in chunks:
                success = self._es_delete_guid_bulk(cls, chunk, app=app, level=new_level)
                total += success

            if level == 0:
                failed = len(guids) - total
                if failed > 0:
                    log.error('Bulk ES delete failed for %d items' % (failed,))

            return total

        # We only update the indexed timestamps of the objects that succeded as a group
        all_guids = cls.query.with_entities(cls.guid).all()
        all_guids = {str(item[0]) for item in all_guids}

        invalid_guids = set(pending) & all_guids
        if len(invalid_guids) > 0:
            if ELASTICSEARCH_VERBOSE:
                log.info('Invalidating (Bulk) {}'.format(cls.__name__))
            with db.session.begin(subtransactions=True):
                db.session.execute(
                    cls.bulk_class()
                    .__table__.update()
                    .values(updated=datetime.datetime.utcnow())
                    .where(cls.bulk_class().guid.in_(invalid_guids))
                )

        # Refresh the index
        es_refresh_index(index, app=app)

        total = len(actions) + len(skipped)
        return total

    def enter(self):
        if self.in_bulk_mode():
            if self.config is not None and len(self.config) > 0:
                top_config = self.depth[0]
                new_config = self.config
                top_json = json.dumps(top_config, sort_keys=True)
                new_json = json.dumps(new_config, sort_keys=True)
                if top_json != new_json:
                    log.warning(
                        'Nested ES sessions respect the config of the top-level context, ignoring config %r and using %r instead'
                        % (
                            new_config,
                            top_config,
                        )
                    )
        else:
            self.reset()
        self.depth.append(self.config)
        self.config = {}

    def exit(self):
        from app.extensions.elasticsearch import tasks as es_tasks

        global CELERY_ASYNC_PROMISES

        if not self.in_bulk_mode():
            self.reset()
            return

        config = self.depth.pop()

        if not self.in_bulk_mode():
            self.depth.append(
                None
            )  # Block any sessions that happen in this block from working

            # uh-oh, bad things
            if config is None:
                config = {}

            blocking = config.get('blocking', config.get('foreground', self.blocking))
            verify = config.get('verified', config.get('verify', False))
            disabled = config.get('disabled', not config.get('enabled', True))
            forced = config.get('forced', config.get('force', False))

            keys = self.bulk_actions.keys()

            for cls in keys:
                index = es_index_name(cls)

                if index is None:
                    continue

                cls_bulk_actions = self.bulk_actions.get(cls, {})
                del_items = set(cls_bulk_actions.get('delete', []))
                idx_items = list(set(cls_bulk_actions.get('index', [])))

                if ELASTICSEARCH_VERBOSE:
                    log.debug(
                        'Processing ES exit for %r (%d delete, %d index)'
                        % (
                            cls,
                            len(del_items),
                            len(idx_items),
                        )
                    )

                if disabled or is_disabled():
                    if ELASTICSEARCH_VERBOSE:
                        log.debug('...disabled')
                    continue

                # Delete all of the delete items
                if len(del_items) > 0:
                    if es_index_exists(index, app=self.app):
                        del_items_ = list(del_items)
                        if blocking:
                            total = len(del_items_)
                            success = self._es_delete_guid_bulk(
                                cls, del_items_, app=self.app
                            )
                            if success < total:  # pragma: no cover
                                log.warning(
                                    'Bulk delete had %d successful items out of %d'
                                    % (
                                        success,
                                        total,
                                    )
                                )
                        else:
                            signature = es_tasks.es_task_delete_guid_bulk.s(
                                index, del_items_
                            )
                            signature.retries = 3
                            promise = signature.apply_async()
                            CELERY_ASYNC_PROMISES.append((signature, promise))

                # Filter out any items that were just deleted
                items = []
                for item in idx_items:
                    obj, force = item
                    if str(obj.guid) in del_items:
                        continue
                    item = (
                        obj,
                        force or forced,
                    )
                    items.append(item)

                # Index everything that isn't deleted
                if len(items) > 0:
                    # Index all items
                    if blocking:
                        total = len(items)
                        success = self._es_index_bulk(cls, items, app=self.app)
                        if success < total:  # pragma: no cover
                            log.warning(
                                'Bulk index had %d successful items out of %d'
                                % (
                                    success,
                                    total,
                                )
                            )
                    else:
                        items = [(str(item.guid), force) for item, force in items]
                        signature = es_tasks.es_task_index_bulk.s(index, items)
                        signature.retries = 3
                        promise = signature.apply_async()
                        CELERY_ASYNC_PROMISES.append((signature, promise))

            # Reset the depth back to zero now that we are done
            placeholder = self.depth.pop()
            assert placeholder is None
            assert not self.in_bulk_mode()

            self.reset()

            if verify:
                self.verify()

    def verify(self, timeout=CELERY_VERIFY_TIMEOUT):
        status = None
        message = True
        verify_timestamp = datetime.datetime.utcnow()
        while True:
            now = datetime.datetime.utcnow()
            delta = now - verify_timestamp
            waiting = delta.total_seconds()
            if waiting >= timeout:
                log.error(status)
                log.error(
                    'ES session was unable to verify after {} seconds'.format(timeout)
                )
                raise RuntimeError('Could not verify')

            status = es_status(outdated=False, health=False)
            if len(status) == 0:
                break

            if message:
                message = False
                if ELASTICSEARCH_VERBOSE:
                    log.info('Waiting for ES session to verify...')

            time.sleep(1.0)

        if not message:
            if ELASTICSEARCH_VERBOSE:
                log.info('...verified')

        return True

    def check(self, limit):
        limit_timestamp = datetime.datetime.utcnow() - datetime.timedelta(seconds=limit)
        if self.timestamp < limit_timestamp:
            delta = limit_timestamp - self.timestamp
            self.abort(
                reason='Timestamp validation failure: timestamp = %r, limit = %r, delta = %r'
                % (
                    self.timestamp,
                    limit_timestamp,
                    delta,
                )
            )

    def abort(self, reason=None):
        if self.in_bulk_mode():
            log.warning('ELASTICSEARCH SESSION ABORT ({!r})'.format(reason))
            # Purge any None values in the depth stack
            self.depth = [item for item in self.depth if item is not None]
            # Take the highest-level non-None config
            if self.in_bulk_mode():
                self.depth = self.depth[:1]
            self.exit()
            self.reset()

    def __enter__(self):
        return self.enter()

    def __exit__(self, type_, value, traceback):
        if type_ is not None or value is not None or traceback is not None:
            self.abort(reason='Exception on __exit__()')
        else:
            try:
                return self.exit()
            except (Exception, sqlalchemy.exc.InvalidRequestError):
                self.abort(reason='Exception on exit()')
                raise HoustonException(log, 'Elasticsearch context failure')


def is_enabled():
    return ENABLED


def is_disabled():
    return not is_enabled()


def off():
    global ENABLED

    if is_enabled():
        log.warning('DISABLING ELASTICSEARCH')
        ENABLED = False


def on():
    global ENABLED

    if is_disabled():
        log.warning('ENABLING ELASTICSEARCH')
        ENABLED = True


def check_celery(verbose=True, revoke=False):
    from app.extensions.celery import celery

    global CELERY_ASYNC_PROMISES

    active = []
    for signature, promise in CELERY_ASYNC_PROMISES:
        if promise.ready():
            status = promise.result
            if not status:
                if revoke:
                    log.warning('Celery task ID {!r} dropped'.format(promise.task_id))
                elif signature.retries > 0:
                    log.warning(
                        'Celery task ID %r failed (retrying %d)'
                        % (
                            promise.task_id,
                            signature.retries,
                        )
                    )
                    signature.retries -= 1
                    promise_ = signature.delay()
                    active.append((signature, promise_))
                else:
                    log.error(
                        'Celery task ID {!r} failed (no reties left)'.format(
                            promise.task_id
                        )
                    )
                    log.error(signature)
        else:
            if revoke:
                celery.control.revoke(promise.task_id, terminate=True)
            else:
                active.append((signature, promise))

    CELERY_ASYNC_PROMISES = active

    num_active = len(CELERY_ASYNC_PROMISES)

    if verbose:
        log.info('Active Celery tasks: %d' % (num_active,))

    return num_active


def shutdown_celery(verbose=False):
    from app.extensions.celery import celery

    # Clear out the current promises
    check_celery(verbose=verbose)

    for signature, promise in CELERY_ASYNC_PROMISES:  # pragma: no cover
        celery.control.revoke(promise.task_id, terminate=True)

    num_active = check_celery(verbose=verbose)
    assert num_active == 0


def register_elasticsearch_model(cls):
    global REGISTERED_MODELS
    REGISTERED_MODELS[cls] = {
        'status': False,
        'pit': None,
    }


def es_index_name(cls, app=None, quiet=False):
    from flask import current_app

    if app is None:
        app = current_app

    if is_disabled():
        return None

    if cls not in REGISTERED_MODELS:
        if not quiet:
            log.error('Model ({!r}) is not in Elasticsearch'.format(cls))
        return None

    index = ('{}.{}'.format(cls.__module__, cls.__name__)).lower()

    if app.testing:
        index = '{}.{}'.format(
            TESTING_PREFIX,
            index,
        )

    return index


def es_index_class(index):
    import inspect
    import sys

    if index is None:
        return None

    index_ = index.strip().strip('.')

    # Remove any testing prefixes
    prefix = '{}.'.format(TESTING_PREFIX)
    if index_.startswith(prefix):
        index_ = index_[len(prefix) :]
        index_ = index_.strip().strip('.')

    index_ = index_.split('.')
    module_ = '.'.join(index_[:-1])
    class_ = index_[-1]

    module = sys.modules.get(module_, None)
    cls = None
    if module is not None:
        clsmembers = inspect.getmembers(module, inspect.isclass)
        for name_, cls_ in clsmembers:
            if name_.lower() == class_:
                cls = cls_

    return cls


def es_health_and_stats(app=None):
    from flask import current_app

    if app is None:
        app = current_app

    health = app.es.cluster.health()
    stats = app.es.indices.stats()

    return health, stats


def es_invalidate(obj):
    if obj is not None:
        with session.begin(disabled=True):
            with db.session.begin(subtransactions=True):
                cls = obj.__class__
                db.session.execute(
                    cls.bulk_class()
                    .__table__.update()
                    .values(updated=datetime.datetime.utcnow())
                    .where(cls.bulk_class().guid == obj.guid)
                )


def es_validate(obj):
    if obj is not None:
        with session.begin(disabled=True):
            with db.session.begin(subtransactions=True):
                cls = obj.__class__
                db.session.execute(
                    cls.bulk_class()
                    .__table__.update()
                    .values(indexed=datetime.datetime.utcnow())
                    .where(cls.bulk_class().guid == obj.guid)
                )


def es_index(obj, app=None, force=False, quiet=False, recover=True):
    from flask import current_app

    if app is None:
        app = current_app

    cls = obj.__class__
    index = es_index_name(cls, app=app, quiet=quiet)

    if index is None:
        return None

    if session.in_bulk_mode():
        return session.track_bulk_action('index', obj, force=force)

    try:
        index, id_, body = obj.serialize()
        resp = app.es.index(index=index, id=id_, body=body)

        _seq_no = resp.get('_seq_no', None)
        if _seq_no is not None and _seq_no == 0:
            # We have indexed our very first object, let's check the mappings
            es_index_mappings_patch(cls, app=app)
            cls.pit(app=app)
    except (
        elasticsearch.exceptions.RequestError,
        TypeError,
    ) as exception:  # pragma: no cover
        if not recover:
            raise

        try:
            # We want to try to recover by checking the index's mappings and try re-indexing
            es_index_mappings_patch(cls, app=app)
            es_index(obj, app=app, force=force, quiet=quiet, recover=False)
        except Exception:
            log.error('Error indexing {!r}, likely bad schema'.format(obj))
            raise exception  # Raise original exception

    # Update the object's indexed timestamp
    assert resp['_id'] == str(obj.guid)
    if resp['result'] in ('created', 'updated'):
        obj.validate()
    else:
        log.error('Database update on an ES model without ES index update')

    if hasattr(obj, 'index_hook_obj'):
        obj.index_hook_obj(app=app, force=force, quiet=quiet)

    # Refresh the index
    es_refresh_index(index, app=app)

    return resp


def es_all_indices(app=None):
    from flask import current_app

    if is_disabled():
        return []

    if app is None:
        app = current_app

    stats = app.es.indices.stats()
    indices = sorted(stats['indices'].keys())

    response = []
    for index in indices:
        if not index.startswith('.'):
            response.append(index)

    return response


def es_create_index(cls, app=None, mappings=None):
    from flask import current_app

    if is_disabled():
        return False

    if app is None:
        app = current_app

    index = es_index_name(cls, app=app)

    if index is None:
        return None

    if es_index_exists(index, app=app):
        return 'exists'

    body = {}

    settings = cls.get_elasticsearch_settings()
    if settings is not None:
        body['settings'] = settings

    if mappings is not None:
        body['mappings'] = {'_doc': {'properties': mappings}}
        include_type_name = True
    else:
        include_type_name = False

    response = app.es.indices.create(
        index, body=body, include_type_name=include_type_name
    )
    acknowledged = response.get('acknowledged', False)

    cls.pit(app=app)

    return acknowledged


def es_delete_index(index, app=None):
    from flask import current_app

    if is_disabled():
        return False

    if app is None:
        app = current_app

    if not es_index_exists(index, app=app):
        return None

    response = app.es.indices.delete(index)
    acknowledged = response.get('acknowledged', False)

    return acknowledged


def es_refresh_index(index, app=None):
    from flask import current_app

    if is_disabled():
        return False

    if app is None:
        app = current_app

    if not es_index_exists(index, app=app):
        return None

    app.es.indices.refresh(index)


def es_add(*args, **kwargs):
    return es_index(*args, **kwargs)


def es_insert(*args, **kwargs):
    return es_index(*args, **kwargs)


def es_set(*args, **kwargs):
    return es_index(*args, **kwargs)


def es_update(*args, **kwargs):
    return es_index(*args, **kwargs)


def es_exists(obj, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    id_ = str(obj.guid)
    cls = obj.__class__
    index = es_index_name(cls, app=app)

    if index is None:
        obj.invalidate()
        return False

    exists = app.es.exists(index, id=id_)

    if not exists:
        obj.invalidate()

    return exists


def es_index_exists(index, app=None):
    from flask import current_app

    if is_disabled():
        return False

    if app is None:
        app = current_app

    return app.es.indices.exists(index)


def es_index_mappings(index, app=None):
    from flask import current_app

    if is_disabled():
        return {}

    if app is None:
        app = current_app

    if not es_index_exists(index, app=app):
        return None

    resp = app.es.indices.get_mapping(index)
    mappings = resp.get(index, {}).get('mappings', {}).get('properties', {})

    return mappings


def es_index_mappings_patch(cls, app=None, quiet=False):
    from copy import deepcopy

    from deepdiff import DeepDiff
    from flask import current_app

    if app is None:
        app = current_app

    if is_disabled():
        return None

    if cls not in REGISTERED_MODELS:
        if not quiet:
            log.error('Model ({!r}) is not in Elasticsearch'.format(cls))
        return None

    if not hasattr(cls, 'patch_elasticsearch_mappings'):
        return None

    index = es_index_name(cls, app=app)

    if not es_index_exists(index, app=app):
        return None

    mappings = es_index_mappings(index)
    if len(mappings) == 0:
        # We don't have a useful "starting" mapping from the auto-parsing, skip
        return None

    # We want to give the developer of `patch_elasticsearch_mappings` the most freedom,
    # can use by-reference updates or returned value

    patched_mappings = deepcopy(mappings)
    patched_mappings = cls.patch_elasticsearch_mappings(patched_mappings)

    diff = DeepDiff(mappings, patched_mappings)
    if len(diff) > 0:
        log.error('Index ({!r}) has an incorrect mapping, rebuilding'.format(index))
        log.error(pprint.pformat(diff))

        # Get all of the GUIDs that have been indexed for this class
        es_refresh_index(index, app=app)
        existsing_guids = cls.elasticsearch(None, load=False)

        # Delete the current idnex
        es_delete_index(index)

        # Recreate the index with the correct mappings
        es_create_index(cls, app=app, mappings=patched_mappings)

        # Restore the msissing GUIDs (in the background)
        with session.begin(forced=True):
            objs = cls.query.filter(cls.guid.in_(existsing_guids)).all()
            desc = 'Restoring {}'.format(cls.__name__)
            for obj in tqdm.tqdm(objs, desc=desc, disable=quiet):
                obj.index(app=app)

        es_refresh_index(index, app=app)

        return 'patched'

    return 'up-to-date'


def es_get(obj, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    id_ = str(obj.guid)
    cls = obj.__class__
    index = es_index_name(cls, app=app)

    if index is None:
        return None

    if not app.es.exists(index, id=id_):
        return None

    resp = app.es.get(index, id=id_)

    assert resp['_id'] == id_

    return resp


def es_search(index, body, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    if not es_index_exists(index, app=app):
        return None

    resp = list(
        helpers.scan(
            app.es, query=body, index=index, scroll='1d', preserve_order=True, size=10000
        )
    )

    return resp


def es_delete(obj, app=None):
    cls = obj.__class__
    return es_delete_guid(cls, obj.guid, app=app)


def es_delete_guid(cls, guid, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    index = es_index_name(cls, app=app)

    if session.in_bulk_mode():
        return session.track_bulk_action('delete', (cls, guid))

    obj = cls.query.get(guid)

    if index is None:
        if obj is not None:
            if hasattr(obj, 'invalidate'):
                obj.invalidate()
        return None

    if not es_index_exists(index, app=app):
        if obj is not None:
            obj.invalidate()
        return None

    id_ = str(guid)
    if not app.es.exists(index, id=id_):
        if obj is not None:
            obj.invalidate()
        return None

    resp = app.es.delete(index, id=id_)

    assert resp['_id'] == id_
    if resp['result'] in ('deleted',):
        if obj is not None:
            obj.invalidate()
    else:
        log.error('Database delete on an ES model without ES index delete')

    # Refresh the index
    es_refresh_index(index, app=app)

    return resp


def es_pit(cls, app=None):
    from flask import current_app

    global REGISTERED_MODELS

    if app is None:
        app = current_app

    index = es_index_name(cls, app=app)

    if index is None:
        return None

    if not es_index_exists(index, app=app):
        return None

    pit_id = REGISTERED_MODELS.get(cls, {}).get('pit', None)
    if pit_id is not None:
        body = {
            'id': pit_id,
        }
        try:
            resp = app.es.close_point_in_time(body)
            assert resp['succeeded']
        except elasticsearch.exceptions.NotFoundError:
            pass

    resp = app.es.open_point_in_time(index, keep_alive='1d')
    pit_id = resp.get('id', None)
    REGISTERED_MODELS[cls]['pit'] = pit_id

    return pit_id


def es_status(app=None, outdated=True, missing=False, active=True, health=True):
    from flask import current_app

    if app is None:
        app = current_app

    status = {}

    if outdated:
        for cls in REGISTERED_MODELS:
            index = es_index_name(cls, app=app)
            if index is None:
                continue

            # Get outdated
            num_outdated = cls.query.filter(cls.updated > cls.indexed).count()
            if num_outdated > 0:
                key = '{}:outdated'.format(index)
                status[key] = num_outdated

    if missing:
        for cls in REGISTERED_MODELS:
            index = es_index_name(cls, app=app)
            if index is None:
                continue

            local_guids = cls.query.with_entities(cls.guid).all()
            local_guids = {item[0] for item in local_guids}

            outdated_guids = (
                cls.query.filter(cls.updated > cls.indexed).with_entities(cls.guid).all()
            )
            outdated_guids = {item[0] for item in outdated_guids}

            es_guids = es_elasticsearch(app, cls, {}, load=False, limit=None)
            es_guids = set(es_guids)

            missing_guids = local_guids - es_guids
            extra_guids = es_guids - local_guids

            num_missing = len(missing_guids)
            if num_missing > 0:
                key = '{}:missing'.format(index)
                status[key] = num_missing

            num_extra = len(extra_guids)
            if num_extra > 0:
                key = '{}:extra'.format(index)
                status[key] = num_extra

            # Update outdated number to remove any that are missing
            key = '{}:outdated'.format(index)
            status.pop(key, None)
            num_outdated = len(outdated_guids - missing_guids)
            if num_outdated > 0:
                status[key] = num_outdated

    if active:
        num_active = check_celery(verbose=False)
        if num_active > 0:
            status['celery:active'] = num_active

    if health:
        if is_disabled():
            status['elasticsearch:enabled'] = False

        health_data, stats_data = es_health_and_stats(app=app)
        if health_data['status'] != 'green':
            status['status'] = health_data['status']

    return status


def es_serialize_parallel_worker(obj):
    from flask import current_app

    app = current_app

    try:
        data = obj.serialize(app=app)
    except Exception:  # pragma: no cover
        data = None
    return data


def es_serialize_parallel(objs, desc=None, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    failures = []
    with app.test_request_context():
        results = executor.map(es_serialize_parallel_worker, objs)
        datas = []
        for obj, data in tqdm.tqdm(zip(objs, results), total=len(objs), desc=desc):
            if data is None:
                failures.append(obj)
                data = obj.serialize(app=app)
            datas.append(data)

    if len(failures) > 0:
        log.warning(
            'Parallel had to use serial fallback for %d images' % (len(failures),)
        )

    return datas


def es_serialize(obj, allow_schema=True, app=None):
    def _check_value(value):

        retval = RuntimeError

        # Check if this is any type of function, method, or database object
        if isinstance(
            value,
            (
                db.Model,
                enum.EnumMeta,
                types.MethodType,
                types.FunctionType,
                types.BuiltinFunctionType,
                types.MethodWrapperType,
                flask_sqlalchemy.BaseQuery,
                flask_sqlalchemy.model.DefaultMeta,
                sqlalchemy.sql.schema.Table,
                sqlalchemy.sql.schema.MetaData,
                sqlalchemy.orm.Mapper,
                sqlalchemy.orm.state.InstanceState,
                sqlalchemy.orm.instrumentation.ClassManager,
                sqlalchemy_utils.types.password.Password,
                weakref.WeakValueDictionary,
                werkzeug.local.LocalProxy,
            ),
        ):
            raise ValueError()

        # Check if we are looking at an iterable or dict of valid items
        if isinstance(value, (list, tuple, set)):
            retval = []
            for item in value:
                retval.append(_check_value(item))

        if isinstance(value, dict):
            retval = {}
            for key in value:
                retval[key] = _check_value(value[key])

        # Check specific data types that we should be able to serialize
        if isinstance(value, uuid.UUID):
            retval = str(value)
        if isinstance(value, datetime.date):
            retval = value.strftime('%Y-%m-%dT%H:%M:%S%z')
        if isinstance(obj, datetime.time):
            retval = value.strftime('%H:%M:%S')

        # Default assignment
        if retval == RuntimeError:
            retval = value

        return retval

    cls = obj.__class__

    index = es_index_name(cls, app=app)
    assert index is not None

    if allow_schema and hasattr(cls, 'get_elasticsearch_schema'):
        schema = cls.get_elasticsearch_schema()
    else:
        schema = None

    if schema is not None:
        try:
            body = schema().dump(obj).data
        except Exception as ex:  # pragma: no cover
            _, _, body = es_serialize(obj, allow_schema=False, app=app)
            body['guid'] = str(obj.guid)
            body['_schema'] = '{} (failed with {!r}: {})'.format(
                body['_schema'],
                schema.__name__,
                ex,
            )
            body['indexed'] = f'{datetime.datetime.utcnow().isoformat()}+00:00'
            return index, obj.guid, body
    else:
        try:
            body = {}
            skipped = []
            for attr in sorted(dir(obj)):
                # Get rid of Python and SQLAlchemy specific attributes
                if attr in (
                    '__dict__',
                    '__weakref__',
                    '__table_args__',
                    'query_class',
                    'password',  # explicitly do not send this to ES
                ):
                    continue

                value = getattr(obj, attr)
                try:
                    value = _check_value(value)
                except ValueError:  # pragma: no cover
                    continue
                except AttributeError:  # pragma: no cover
                    raise AttributeError('Could not check attr = {!r}'.format(attr))

                # ensure that we can serlialize this information
                try:
                    json.dumps(value)
                except TypeError:  # pragma: no cover
                    skipped.append(attr)
                    continue

                body[attr] = value

            if len(skipped) > 0:
                log.warning(
                    'Skipping Elasticsearch attributes %r for class %r'
                    % (
                        len(skipped),
                        cls,
                    )
                )
        except Exception as ex:  # pragma: no cover
            body = {}
            body['guid'] = str(obj.guid)
            body['_schema'] = 'automatic (failed: {})'.format(ex)
            body['indexed'] = f'{datetime.datetime.utcnow().isoformat()}+00:00'
            return index, obj.guid, body

    if schema is None:
        body['_schema'] = 'automatic'
    else:
        body['_schema'] = schema.__name__
    body['indexed'] = f'{datetime.datetime.utcnow().isoformat()}+00:00'
    body.pop('elasticsearchable', None)

    return index, obj.guid, body


def attach_listeners(app):
    from sqlalchemy.event import listen

    global REGISTERED_MODELS

    def _before_insert_or_update(mapper, connection, obj):
        try:
            if obj.guid is not None:
                obj.index(app=app, force=True)
        except Exception:  # pragma: no cover
            log.error('ES index update failed for {!r}'.format(obj))
            raise

    def _before_delete(mapper, connection, obj):
        try:
            obj.prune(app=app)
        except Exception:  # pragma: no cover
            log.error('ES index delete failed for {!r}'.format(obj))
            raise

    def _create_transaction(db_session, db_transaction):
        session.begin().enter()

    def _end_transaction(db_session, db_transaction):
        session.exit()

    for cls in REGISTERED_MODELS:
        # Only register this hook once
        if not REGISTERED_MODELS[cls]['status']:
            if ELASTICSEARCH_VERBOSE:
                name = '{}.{}'.format(cls.__module__, cls.__name__)
                log.info('Attach Elasticsearch listener for {!r}'.format(name))
            listen(cls, 'before_insert', _before_insert_or_update, propagate=True)
            listen(cls, 'before_update', _before_insert_or_update, propagate=True)
            listen(cls, 'before_delete', _before_delete, propagate=True)
            REGISTERED_MODELS[cls]['status'] = True

    listen(db.session, 'after_transaction_create', _create_transaction, propagate=True)
    listen(db.session, 'after_transaction_end', _end_transaction, propagate=True)


def es_index_all(*args, **kwargs):
    for cls in REGISTERED_MODELS:
        cls.index_all(*args, **kwargs)


def es_prune_all(*args, **kwargs):
    for cls in REGISTERED_MODELS:
        cls.prune_all(*args, **kwargs)


def es_invalidate_all(*args, **kwargs):
    for cls in REGISTERED_MODELS:
        cls.invalidate_all(*args, **kwargs)


def es_pit_all(*args, **kwargs):
    for cls in REGISTERED_MODELS:
        cls.pit(*args, **kwargs)


def es_checkpoint(*args, **kwargs):
    timeout = kwargs.pop('timeout', CELERY_VERIFY_TIMEOUT)
    session.verify(timeout=timeout)
    es_refresh_all(*args, **kwargs)
    session.verify(timeout=timeout)


def es_refresh_all(*args, **kwargs):
    for cls in REGISTERED_MODELS:
        index = es_index_name(cls)

        if index is None:
            continue

        es_refresh_index(index, *args, **kwargs)


def es_elasticsearch(
    app,
    cls,
    body,
    prune=True,
    load=True,
    limit=100,
    offset=0,
    sort='guid',
    reverse=False,
    reverse_after=False,
    filter_guids=None,
    total=False,
):
    index = es_index_name(cls)

    if index is None:
        if total:
            return 0, []
        else:
            return []

    # Don't return anything about the hits
    assert isinstance(body, dict)
    assert sort.count('.') <= 1
    body['_source'] = False

    pre_sorted = sort.startswith(ELASTICSEARCH_SORTING_PREFIX)

    if pre_sorted:
        es_sort_term = sort.replace(ELASTICSEARCH_SORTING_PREFIX, '')
        es_sort_order = 'desc' if reverse else 'asc'
        body['sort'] = [
            {
                es_sort_term: {'order': es_sort_order},
            },
            {
                'guid': {'order': es_sort_order},
            },
        ]

    try:
        hits = es_search(index, body, app=app)
    except (elasticsearch.exceptions.RequestError, TypeError):  # pragma: no cover
        if 'sort' in body:
            # Try again without any sort field in the body
            es_sort = body.pop('sort')
            log.error(
                'Unable to sort within Elasticsearch using {!r}, retrying without sort'.format(
                    es_sort
                )
            )

            # Remove ES-specific prefix from sort
            # This will also try to use local columns as a backup, if found
            sort = sort.replace(ELASTICSEARCH_SORTING_PREFIX, '')
            pre_sorted = False

            hits = es_search(index, body, app=app)
        else:
            raise

    if hits is None or len(hits) == 0:
        if total:
            return 0, []
        else:
            return []

    # Get all hits from the search
    hit_guids = []
    for hit in hits:
        guid = uuid.UUID(hit['_id'])
        hit_guids.append(guid)

    # Get all possible corect matches
    all_guids = cls.query.with_entities(cls.guid).all()
    all_guids = {item[0] for item in all_guids}

    if filter_guids is None:
        filter_guids = all_guids
    filter_guids = set(filter_guids)

    # Cross reference with ES hit GUIDs
    search_guids = []
    search_prune = []
    for guid in hit_guids:
        if guid in all_guids:
            if guid in filter_guids:
                search_guids.append(guid)
        else:
            search_prune.append(guid)

    if prune and len(search_prune) > 0:
        with session.begin():
            search_prune = list(set(search_prune))
            log.warning(
                'Found %d items to prune for class %r after search in %r'
                % (
                    len(search_prune),
                    cls,
                    index,
                )
            )
            desc = 'Pruning {}'.format(cls.__name__)
            quiet = len(search_prune) < 100
            for guid in tqdm.tqdm(search_prune, desc=desc, disable=quiet):
                es_delete_guid(cls, guid, app=app)

    total_hits = len(search_guids)

    # Get all table GUIDs
    prmiary_columns = list(cls.__table__.primary_key.columns)
    if len(prmiary_columns) > 1:
        default_column = prmiary_columns[0]
    else:
        log.warning('Multiple columns specified as the primary key, defaulting to GUID')
        default_column = cls.guid

    sort = sort.lower()
    outerjoin_cls = None

    if pre_sorted:
        # The results we pre-sorted by Elasticsearch during the query, just fetch them
        # We will re-order them after load
        sort_column = default_column
    elif sort in ['default', 'primary']:
        sort_column = default_column
    else:
        # First, check for columns in the table
        sort_column = None
        column_names = list(cls.__table__.columns)
        for column in column_names:
            if column.name.lower() == sort:
                sort_column = column

        # Next, check for columns in relationship tables
        if '.' in sort:
            for attribute, relationship in inspect(cls).relationships.items():
                rel_cls = relationship.mapper.class_
                column_names = list(rel_cls.__table__.columns)
                for column in column_names:
                    column_name = '{}.{}'.format(
                        attribute,
                        column.name.lower(),
                    )
                    if column_name == sort:
                        outerjoin_cls = rel_cls
                        sort_column = column

        if sort_column is None:
            log.warning(
                'The sort field {!r} is unrecognized, defaulting to GUID'.format(sort)
            )
            sort_column = default_column

    sort_func_1 = sort_column.desc if reverse else sort_column.asc
    sort_func_2 = default_column.desc if reverse else default_column.asc

    query = cls.query

    if outerjoin_cls is not None:
        query = query.outerjoin(outerjoin_cls)

    query = query.filter(cls.guid.in_(search_guids))

    if pre_sorted:
        # We pre-sorted, so let's do all filtering on the GUIDs here since the query is being broken up here
        query = query.with_entities(cls.guid)

        houston_guids = query.all()
        houston_guids = {local_result[0] for local_result in houston_guids}

        elasticsearch_guids = []
        for search_guid in search_guids:
            if search_guid in houston_guids:
                elasticsearch_guids.append(search_guid)

        if offset is not None:
            offset = max(0, min(offset, len(elasticsearch_guids)))
            elasticsearch_guids = elasticsearch_guids[offset:]

        if limit is not None:
            offset = max(0, min(limit, len(elasticsearch_guids)))
            elasticsearch_guids = elasticsearch_guids[:limit]

        if reverse_after:
            elasticsearch_guids = elasticsearch_guids[::-1]

        if load:
            results = []
            for elasticsearch_guid in elasticsearch_guids:
                obj = cls.query.get(elasticsearch_guid)
                if (
                    obj
                ):  # This should always be True since we have already filtered on the DB
                    results.append(obj)
        else:
            results = elasticsearch_guids
    else:
        # We are performing a Houston-forward SQL query, so let's stay within SQLalchemy for as long as possible
        query = query.order_by(sort_func_1(), sort_func_2()).offset(offset).limit(limit)

        if reverse_after:
            after_sort_func_1 = sort_column.asc if reverse else sort_column.desc
            after_sort_func_2 = default_column.asc if reverse else default_column.desc
            query = query.from_self().order_by(after_sort_func_1(), after_sort_func_2())

        if not load:
            query = query.with_entities(cls.guid)

        results = query.all()

        if not load:
            # Strip column 0
            results = [result[0] for result in results]

    if total:
        return total_hits, results
    else:
        return results


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    global session

    app.elasticsearch = elasticsearch.Elasticsearch(
        hosts=app.config['ELASTICSEARCH_HOSTS'],
        http_auth=app.config['ELASTICSEARCH_HTTP_AUTH'],
    )
    app.es = app.elasticsearch

    # Setup Elasticsearch session handle
    session = ElasticSearchBulkOperation(app=app)

    api_v1.add_oauth_scope('search:read', 'Provide access to search')

    # Touch underlying modules
    from . import resources  # NOQA

    api_v1.add_namespace(resources.api)
