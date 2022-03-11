# -*- coding: utf-8 -*-
""" Client initialization for Elasticsearch """
from gumby import Client, initialize_indexes_by_model

from app.extensions import is_extension_enabled, db

import elasticsearch
from elasticsearch import helpers

import logging

from flask import current_app
import flask_sqlalchemy
import utool as ut
import sqlalchemy_utils
import sqlalchemy
import threading
import datetime
import werkzeug
import weakref

import uuid
import types
import tqdm
import json
import enum


if not is_extension_enabled('elasticsearch'):
    raise RuntimeError('Elastic Search is not enabled')


TESTING_PREFIX = 'testing'
REGISTERED_MODELS = {}

CELERY_ASYNC_PROMISES = []


bulk_lock = threading.Lock()


log = logging.getLogger('elasticsearch')  # pylint: disable=invalid-name


session = None


class ElasticsearchModel(object):
    """Adds `viewed` column to a derived declarative model."""

    @classmethod
    def get_elasticsearch_schema(cls):
        return None

    @classmethod
    def index_hook_cls(cls):
        pass

    @classmethod
    def pit(cls, *args, **kwargs):
        return es_pit(cls, *args, **kwargs)

    @classmethod
    def _index(cls):
        return get_elasticsearch_index_name(cls)

    @classmethod
    def index_all(cls, app=None, prune=True, pit=False, update=True, force=False):
        index = cls._index()

        if index is None:
            return

        with session.begin():
            if prune:
                # Delete anything from the index that is not in the database
                indexed_guids = set(cls.elasticsearch(search={}, app=app, load=False))

            if pit:
                # Establish a new point-in-time
                cls.pit(app=app)

            if update:
                all_guids = cls.query.with_entities(cls.guid).all()
                all_guids = set([item[0] for item in all_guids])

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
                    outdated_guids = set([item[0] for item in outdated_guids])

                guids = list(missing_guids | outdated_guids)
                log.info(
                    'Elasticsearch Index All %r into %r (%d items, force=%r)'
                    % (
                        cls,
                        index,
                        len(guids),
                        force,
                    )
                )
                # Re-index all objects in our local database
                for guid in guids:
                    obj = cls.query.get(guid)
                    obj.index(app=app, force=force)

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
            response = elasticsearch_on_class(app, cls, body, *args, **kwargs)

        return response

    @property
    def index_name(self):
        return self.__class__._index()

    @property
    def elasticsearchable(self):
        return self.indexed >= self.updated

    def index_hook_obj(self):
        return self.__class__.index_hook_cls()

    def index(self, *args, **kwargs):
        return self._elasticsearch_index(*args, **kwargs)

    def fetch(self, *args, **kwargs):
        return self._elasticsearch_get(*args, **kwargs)

    def prune(self, *args, **kwargs):
        return self._elasticsearch_delete(*args, **kwargs)

    def _elasticsearch_exists(self, *args, **kwargs):
        return es_exists(self, *args, **kwargs)

    def _elasticsearch_index(self, *args, **kwargs):
        return es_index(self, *args, **kwargs)

    def _elasticsearch_get(self, *args, **kwargs):
        return es_get(self, *args, **kwargs)

    def _elasticsearch_update(self, *args, **kwargs):
        return es_update(self, *args, **kwargs)

    def _elasticsearch_delete(self, *args, **kwargs):
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

    def track_bulk_action(self, action, item, force=False):
        log.debug(
            'Tracking %r action for %r (force = %r)'
            % (
                action,
                item,
                force,
            )
        )

        if self.in_skip_mode():
            log.debug('...skipped')
            return 'skipped'

        action = action.lower().strip()

        if action == 'index':
            cls = item.__class__
            item = (item, force)
        elif action == 'delete':
            cls, guid = item
            item = str(guid)
        else:
            raise RuntimeError()

        if cls not in self.bulk_actions:
            self.bulk_actions[cls] = {}
        if action not in self.bulk_actions[cls]:
            self.bulk_actions[cls][action] = []

        self.bulk_actions[cls][action].append(item)
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
        exists = set([])

        if app is None:
            app = self.app

        index = get_elasticsearch_index_name(cls)

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
            total, errors = helpers.bulk(
                app.es, actions, index=index, raise_on_error=False
            )
            for error in errors:
                create = error.get('create', {})
                flag = 'document already exists' in create.get('error', {}).get(
                    'reason', ''
                )
                if flag:
                    guid = create.get('_id', None)
                    if guid in all_guids:
                        exists.add(guid)
        except (AssertionError, helpers.errors.BulkIndexError):
            pass

        return exists

    def _es_index_bulk(self, cls, items, app=None, level=0):
        if app is None:
            app = self.app

        index = get_elasticsearch_index_name(cls)

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

        level_str = '' if level == 0 else ' [retry=%d]' % (level,)
        desc = 'Indexing (Bulk) %s%s' % (
            cls.__name__,
            level_str,
        )

        actions = []
        for obj in tqdm.tqdm(pending, desc=desc):
            index_, id_, body = build_elasticsearch_index_body(obj)
            assert index == index_
            action = body
            action['_id'] = str(id_)
            actions.append(action)

        try:
            total, errors = helpers.bulk(
                app.es, actions, index=index, raise_on_error=False
            )
            assert total == len(actions)
            assert len(errors) == 0
        except (AssertionError, helpers.errors.BulkIndexError):
            if len(items) == 1:
                obj, force = items[0]
                return obj.elasticsearchable

            total = 0
            new_level = level + 1
            chunk_size = max(1, len(items) // 2)
            chunks = list(ut.ichunks(items, chunk_size))
            for chunk in chunks:
                success = self._es_index_bulk(cls, chunk, app=app, level=new_level)
                total += success

            if level == 0:
                failed = len(items) - total
                if failed > 0:
                    log.error('Bulk ES index failed for %d items' % (failed,))

            return total

        # We only update the indexed timestamps of the objects that succeded as a group
        log.info('Time-stamping (Bulk) %s' % (cls.__name__,))
        with db.session.begin(subtransactions=True):
            for obj in pending:
                obj.indexed = datetime.datetime.utcnow()
                db.session.merge(obj)

        total = len(actions) + len(skipped)
        return total

    def _es_delete_guid_bulk(self, cls, guids, app=None, level=0):
        if app is None:
            app = self.app

        index = get_elasticsearch_index_name(cls)

        if index is None:
            return 0

        exists = self._es_exists_bulk(cls, guids, app=app)

        actions = []
        skipped = []
        for guid in guids:
            id_ = str(guid)
            if id_ in exists:
                action = {
                    '_id': id_,
                    '_op_type': 'delete',
                }
                actions.append(action)
            else:
                skipped.append(guid)

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

        if len(actions) == 0:
            return len(skipped)

        try:
            total, errors = helpers.bulk(
                app.es, actions, index=index, raise_on_error=False
            )
            assert total == len(actions)
            assert len(errors) == 0
        except (AssertionError, helpers.errors.BulkIndexError):
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
                            new_json,
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

            blocking = config.get('blocking', self.blocking)
            disabled = config.get('disabled', not config.get('enabled', True))
            forced = config.get('forced', False)

            keys = self.bulk_actions.keys()
            log.debug('ES exit block with %r keys' % (keys,))

            for cls in keys:
                index = get_elasticsearch_index_name(cls)

                if index is None:
                    continue

                cls_bulk_actions = self.bulk_actions.get(cls, {})
                del_items = set(cls_bulk_actions.get('delete', []))
                idx_items = list(set(cls_bulk_actions.get('index', [])))

                log.debug(
                    'Processing ES exit for %r (%d delete, %d index)'
                    % (
                        cls,
                        len(del_items),
                        len(idx_items),
                    )
                )

                if disabled:
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
                            if success < total:
                                log.warning(
                                    'Bulk delete had %d successful items out of %d'
                                    % (
                                        success,
                                        total,
                                    )
                                )
                        else:
                            signature = es_tasks.elasticsearch_delete_guid_bulk.s(
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
                        if success < total:
                            log.warning(
                                'Bulk index had %d successful items out of %d'
                                % (
                                    success,
                                    total,
                                )
                            )
                    else:
                        items = [(str(item.guid), force) for item, force in items]
                        signature = es_tasks.elasticsearch_index_bulk.s(index, items)
                        signature.retries = 3
                        promise = signature.apply_async()
                        CELERY_ASYNC_PROMISES.append((signature, promise))

                # Refresh the index
                es_refresh(index, app=self.app)

            # Reset the depth back to zero now that we are done
            placeholder = self.depth.pop()
            assert placeholder is None
            assert not self.in_bulk_mode()

            self.reset()

    def check(self, limit):
        if self.in_bulk_mode():
            limit_timestamp = datetime.datetime.utcnow() - datetime.timedelta(
                seconds=limit
            )
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
        log.warning('ELASTICSEARCH SESSION ABORT (%r)' % (reason,))
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
            return self.exit()


def check_celery(verbose=True, revoke=False):
    from app.extensions.celery import celery

    global CELERY_ASYNC_PROMISES

    active = []
    for signature, promise in CELERY_ASYNC_PROMISES:
        if promise.ready():
            status = promise.result
            if not status:
                if revoke:
                    log.warning('Celery task ID %r dropped' % (promise.task_id,))
                elif signature.retries > 0:
                    log.warning(
                        'Celery task ID %r failed (retrying %d)'
                        % (
                            promise.task_id,
                            signature.retries,
                        )
                    )
                    signature.retries -= 1
                    promise_ = signature.apply_async()
                    active.append((signature, promise_))
                else:
                    log.error(
                        'Celery task ID %r failed (no reties left)' % (promise.task_id,)
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

    for signature, promise in CELERY_ASYNC_PROMISES:
        celery.control.revoke(promise.task_id, terminate=True)

    num_active = check_celery(verbose=verbose)
    assert num_active == 0


def register_elasticsearch_model(cls):
    global REGISTERED_MODELS
    REGISTERED_MODELS[cls] = {
        'status': False,
        'pit': None,
    }


def get_elasticsearch_index_name(cls):
    if cls not in REGISTERED_MODELS:
        logging.error('Model (%r) is not in Elasticsearch' % (cls,))
        return None

    index = ('%s.%s' % (cls.__module__, cls.__name__)).lower()

    if current_app.testing:
        index = '%s.%s' % (
            TESTING_PREFIX,
            index,
        )

    return index


def get_elasticsearch_cls_from_index(index):
    import sys
    import inspect

    index_ = index.strip().strip('.')

    # Remove any testing prefixes
    prefix = '%s.' % (TESTING_PREFIX,)
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


def es_invalidate(obj):
    if obj is not None and hasattr(obj, 'updated'):
        obj.updated = datetime.datetime.utcnow()


def es_index(obj, init=False, app=None, force=False):
    from flask import current_app

    if app is None:
        app = current_app

    if session.in_bulk_mode():
        return session.track_bulk_action('index', obj, force=force)

    try:
        index, id_, body = build_elasticsearch_index_body(obj)
        resp = app.es.index(index=index, id=id_, body=body)
    except (elasticsearch.exceptions.RequestError, TypeError):
        log.error('Error indexing %r' % (obj,))
        raise

    # Update the object's indexed timestamp
    assert resp['_id'] == str(obj.guid)
    if resp['result'] in ('created', 'updated'):
        obj.indexed = datetime.datetime.utcnow()
    else:
        log.error('Database update on an ES model without ES index update')

    if hasattr(obj, 'index_hook_obj'):
        obj.index_hook_obj()

    if init:
        return resp, index
    else:
        es_refresh(index=index, app=app)
        return resp


def es_all_indices(app=None):
    from flask import current_app

    if app is None:
        app = current_app

    stats = app.es.indices.stats()
    indices = sorted(stats['indices'].keys())

    response = []
    for index in indices:
        if not index.startswith('.'):
            response.append(index)

    return response


def es_delete_index(index, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    response = app.es.indices.delete(index)
    acknowledged = response.get('acknowledged', False)

    return acknowledged


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
    index = get_elasticsearch_index_name(cls)

    if index is None:
        return False

    return app.es.exists(index, id=id_)


def es_index_exists(index, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    return app.es.indices.exists(index)


def es_index_mappings(index, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    resp = app.es.indices.get_mapping(index)
    mappings = resp.get(index, {}).get('mappings', {}).get('properties', {})

    return mappings


def es_index_has_mapping(cls, key, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    index = get_elasticsearch_index_name(cls)

    if index is None:
        return False

    mappings = es_index_mappings(index)

    return key in mappings


def es_get(obj, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    id_ = str(obj.guid)
    cls = obj.__class__
    index = get_elasticsearch_index_name(cls)

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

    resp = list(helpers.scan(app.es, query=body, index=index, scroll='1d'))

    return resp


def es_delete(obj, app=None):
    cls = obj.__class__
    return es_delete_guid(cls, obj.guid, app=app)


def es_delete_guid(cls, guid, app=None):
    from flask import current_app

    if app is None:
        app = current_app

    index = get_elasticsearch_index_name(cls)

    if index is None:
        return None

    if session.in_bulk_mode():
        return session.track_bulk_action('delete', (cls, guid))

    if not es_index_exists(index, app=app):
        return None

    id_ = str(guid)
    if not app.es.exists(index, id=id_):
        return None

    resp = app.es.delete(index, id=id_)

    assert resp['_id'] == id_
    if resp['result'] not in ('deleted'):
        log.error('Database delete on an ES model without ES index delete')

    return resp


def es_refresh(index, app=None):
    # from flask import current_app

    # if app is None:
    #     app = current_app

    # resp = app.es.indices.refresh(index=index)

    # return resp
    pass


def es_pit(cls, app=None):
    from flask import current_app

    global REGISTERED_MODELS

    index = get_elasticsearch_index_name(cls)

    if index is None:
        return None

    if app is None:
        app = current_app

    pit_id = REGISTERED_MODELS.get(cls, {}).get('pit', None)
    if pit_id is not None:
        body = {
            'id': pit_id,
        }
        resp = app.es.close_point_in_time(body)
        assert resp['succeeded']

    if not es_index_exists(index, app=app):
        app.es.indices.create(index)

    resp = app.es.open_point_in_time(index, keep_alive='1d')
    pit_id = resp.get('id', None)
    REGISTERED_MODELS[cls]['pit'] = pit_id

    return pit_id


def es_status(app=None):
    from flask import current_app

    if app is None:
        app = current_app

    status = {}
    for cls in REGISTERED_MODELS:
        index = get_elasticsearch_index_name(cls)
        if index is None:
            continue
        num_guids = cls.query.filter(cls.updated > cls.indexed).count()
        if num_guids > 0:
            status[index] = num_guids

    num_active = check_celery(verbose=False)
    if num_active > 0:
        status['active'] = num_active

    return status


def build_elasticsearch_index_body(obj, allow_schema=True):
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

    index = get_elasticsearch_index_name(cls)
    assert index is not None

    if hasattr(cls, 'get_elasticsearch_schema'):
        schema = cls.get_elasticsearch_schema()
    else:
        schema = None

    if schema is not None and allow_schema:
        try:
            body = schema().dump(obj).data
        except Exception as ex:
            _, _, body = build_elasticsearch_index_body(obj, allow_schema=False)
            body['guid'] = str(obj.guid)
            body['_schema'] = '%s (failed with %r: %s)' % (
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
                except ValueError:
                    continue
                except AttributeError:
                    raise AttributeError('Could not check attr = %r' % (attr,))

                # ensure that we can serlialize this information
                try:
                    json.dumps(value)
                except TypeError:
                    skipped.append(attr)
                    continue

                body[attr] = value

            if len(skipped) > 0:
                log.warning(
                    'Skipping Elasticsearch attributes %r for class %r'
                    % (
                        skipped,
                        cls,
                    )
                )
        except Exception as ex:
            body = {}
            body['guid'] = str(obj.guid)
            body['_schema'] = 'automatic (failed: %s)' % (ex,)
            body['indexed'] = f'{datetime.datetime.utcnow().isoformat()}+00:00'
            return index, obj.guid, body

    if schema is None:
        body['_schema'] = 'automatic'
    else:
        body['_schema'] = schema.__name__
    body['indexed'] = f'{datetime.datetime.utcnow().isoformat()}+00:00'
    body.pop('elasticsearchable', None)

    return index, obj.guid, body


def init_elasticsearch_listeners(app):
    from sqlalchemy.event import listen

    global REGISTERED_MODELS

    def _before_insert_or_update(mapper, connection, obj):
        try:
            if obj.guid is not None:
                obj.index(app=app)
        except Exception:
            log.error('ES index update failed for %r' % (obj,))
            raise

    def _before_delete(mapper, connection, obj):
        try:
            obj.prune(app=app)
        except Exception:
            log.error('ES index delete failed for %r' % (obj,))
            raise

    def _create_transaction(db_session, db_transaction):
        session.begin().enter()

    def _end_transaction(db_session, db_transaction):
        session.exit()

    for cls in REGISTERED_MODELS:
        # Only register this hook once
        if not REGISTERED_MODELS[cls]['status']:
            name = '%s.%s' % (cls.__module__, cls.__name__)
            log.info('Init ES listener model %r' % (name,))
            listen(cls, 'before_insert', _before_insert_or_update)
            listen(cls, 'before_update', _before_insert_or_update)
            listen(cls, 'before_delete', _before_delete)
            REGISTERED_MODELS[cls]['status'] = True

    listen(db.session, 'after_transaction_create', _create_transaction)
    listen(db.session, 'after_transaction_end', _end_transaction)


def init_elasticsearch_index(app, verbose=True, **kwargs):
    for cls in REGISTERED_MODELS:
        # re-index the database
        if verbose:
            name = '%s.%s' % (cls.__module__, cls.__name__)
            log.info('Init ES index model %r' % (name,))

        cls.index_all(app=app, **kwargs)


def elasticsearch_on_class(
    app,
    cls,
    body,
    load=True,
    limit=100,
    offset=0,
    sort='guid',
    reverse=False,
    total=False,
):
    index = get_elasticsearch_index_name(cls)

    if index is None:
        return []

    # Don't return anything about the hits
    assert isinstance(body, dict)
    body['_source'] = False

    hits = es_search(index, body, app=app)

    if hits is None or len(hits) == 0:
        return []

    # Get all hits from the search
    hit_guids = []
    for hit in hits:
        guid = uuid.UUID(hit['_id'])
        hit_guids.append(guid)

    # Get all possible corect matches
    all_guids = cls.query.with_entities(cls.guid).all()
    all_guids = set([item[0] for item in all_guids])

    # Cross reference with ES hit GUIDs
    search_guids = []
    search_prune = []
    for guid in hit_guids:
        if guid in all_guids:
            search_guids.append(guid)
        else:
            search_prune.append(guid)

    total_hits = len(search_guids)

    # Get all table GUIDs
    sort = sort.lower()
    if sort == 'guid':
        sort_column = cls.guid
    else:
        sort_column = None
        for column in list(cls.__table__.columns):
            if column.name.lower() == sort:
                sort_column = column
        if sort_column is None:
            raise ValueError('The sort field %r is unrecognized' % (sort,))

    sort_func = sort_column.desc if reverse else sort_column.asc
    guids = (
        cls.query.filter(cls.guid.in_(search_guids))
        .with_entities(cls.guid)
        .order_by(sort_func())
        .offset(offset)
        .limit(limit)
        .all()
    )
    guids = [item[0] for item in guids]

    if len(search_prune) > 0:
        with session.begin():
            search_prune = list(set(search_prune))
            log.warning(
                'Found %d ids to prune for class %r after search'
                % (
                    len(search_prune),
                    cls,
                )
            )
            for guid in search_prune:
                es_delete_guid(cls, guid, app=app)

    if load:
        objs = []
        for guid in tqdm.tqdm(guids, desc='Loading Hits %s' % (cls.__name__,)):
            obj = cls.query.get(guid)
            objs.append(obj)
        if total:
            return total_hits, objs
        else:
            return objs
    else:
        if total:
            return total_hits, guids
        else:
            return guids


def init_app(app, **kwargs):
    # pylint: disable=unused-argument
    """
    API extension initialization point.
    """
    global session

    hosts = app.config['ELASTICSEARCH_HOSTS']
    app.elasticsearch = Client(hosts)
    app.es = app.elasticsearch

    # Setup Elasticsearch session handle
    session = ElasticSearchBulkOperation(app=app)

    # Initialize indexes if they don't already exists
    initialize_indexes_by_model(using=app.es)
