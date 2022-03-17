# -*- coding: utf-8 -*-
import pytest
import time
import datetime

from tests.utils import (
    extension_unavailable,
    wait_for_elasticsearch_status,
    elasticsearch,
)


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'), reason='Elasticsearch extension disabled'
)
def test_indexing_with_elasticsearch():
    from app.extensions import elasticsearch as es
    from app.modules.users.models import User
    from app.modules.assets.models import AssetTags

    assert User in es.REGISTERED_MODELS
    assert AssetTags not in es.REGISTERED_MODELS

    User.index_all()
    AssetTags.index_all()


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'), reason='Elasticsearch extension disabled'
)
def test_index_cls_conversion():
    from app.extensions import elasticsearch as es
    from app.modules.users.models import User

    index = es.es_index_name(User)
    cls = es.get_elasticsearch_cls_from_index(index)

    if None in [index, cls]:
        assert index is None
        assert cls is None
        assert es.is_disabled()
    else:
        assert es.is_enabled()
        assert cls == User


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'), reason='Elasticsearch extension disabled'
)
def test_elasticsearch_utilities(flask_app_client, db, admin_user, staff_user):
    from app.extensions.elasticsearch import tasks as es_tasks
    from app.extensions import elasticsearch as es
    from app.modules.complex_date_time.models import ComplexDateTime, Specificities
    from app.modules.users.models import User
    from app.modules.users.schemas import UserListSchema

    es.check_celery(revoke=True)
    es.es_checkpoint()
    assert len(es.es_status()) == 0
    assert es.check_celery() == 0

    # Check if we can turn off ES globally
    assert es.is_enabled()
    es.off()
    assert es.is_disabled()
    es.on()
    assert es.is_enabled()

    # Check Point-in-Times (PITs)
    for cls in es.REGISTERED_MODELS:
        index = es.es_index_name(cls)

        data = es.REGISTERED_MODELS[cls]
        assert data.get('status', False)

        old_pit = data.get('pit', None)
        es.es_refresh_index(index)
        new_pit = data.get('pit', None)
        assert old_pit == new_pit

    # Check the schema for a User
    cls = User
    schema = cls.get_elasticsearch_schema()
    assert schema == UserListSchema
    assert admin_user.index_name == es.es_index_name(cls)
    assert admin_user.index_hook_obj() is None

    index, guid, body_schema = es.es_serialize(admin_user)
    assert index == admin_user._index()
    assert guid == admin_user.guid
    assert len(body_schema) > 0
    assert body_schema.get('_schema') == schema.__name__

    # Force building
    index, guid, body_automtic = es.es_serialize(admin_user, allow_schema=False)
    assert index == admin_user._index()
    assert guid == admin_user.guid
    assert len(body_automtic) > 0
    assert body_schema != body_automtic
    assert body_automtic.get('_schema') == 'automatic'

    # Check pruning a specific object when it shouldn't exist
    admin_user.prune()

    # Index object in the foreground
    assert not admin_user.available()
    assert admin_user.available() == es.es_exists(admin_user)
    assert not admin_user.elasticsearchable

    assert admin_user.index().get('result', None) == 'created'
    assert admin_user.index().get('result', None) == 'updated'
    assert admin_user.elasticsearchable
    assert admin_user.available()

    # Alias for indexing
    assert es.es_index(admin_user).get('_id', None) == admin_user.index().get('_id', None)
    assert es.es_add(admin_user).get('_id', None) == admin_user.index().get('_id', None)
    assert es.es_insert(admin_user).get('_id', None) == admin_user.index().get(
        '_id', None
    )
    assert es.es_update(admin_user).get('_id', None) == admin_user.index().get(
        '_id', None
    )

    # Fetch a user's document out of ES
    source = admin_user.fetch().get('_source', {})
    assert es.es_get(admin_user) == admin_user.fetch()
    assert source.get('guid', None) == str(admin_user.guid)
    assert source.get('_schema', None) == schema.__name__

    # Add all users to the index
    with es.session.begin(blocking=True, verify=True):
        assert es.session.in_bulk_mode()

        User.index_all()
        User.index_all(prune=False)
        User.index_all(update=False)
        User.index_all(force=True)

    # Ensure context managers are working correctly
    assert not es.session.in_bulk_mode()
    assert not es.session.in_skip_mode()

    # We can use verify to wait for ES and shards to catch-up
    es.es_checkpoint()

    # Check if the object is showing up in searches
    users = User.elasticsearch(None, load=True)
    assert admin_user in users
    assert staff_user in users
    guids = User.elasticsearch(None, load=False)
    assert admin_user.guid in guids
    assert staff_user.guid in guids

    total1, users1 = User.elasticsearch({}, total=True, load=False)
    assert total1 >= len(users1)
    assert len(users1) <= 100

    # Check refresh and search
    es.es_refresh_index(es.es_index_name(User))

    total2, users2 = User.elasticsearch({}, total=True, load=False)
    assert total1 == total2
    assert users1 == users2

    # Check if we can prune objects
    with es.session.begin(blocking=True, verify=True):
        User.prune_all()

    users = User.elasticsearch(None, load=False)
    assert len(users) == 0

    # Check invalidating
    with es.session.begin(blocking=True, forced=True):
        User.index_all()
    assert es.session.verify()  # verify manually

    # Invalidate a specific user object
    admin_user.invalidate()
    with es.session.begin(blocking=True, verify=True):
        User.index_all()

    total1, users1 = User.elasticsearch({}, total=True, sort='guid')
    total2, users2 = User.elasticsearch({}, total=True, sort='indexed')
    total3, users3 = User.elasticsearch({}, total=True, sort='indexed', reverse=True)
    assert total1 == total2 and total2 == total3
    assert users2 == users3[::-1]
    assert set(users1) == set(users2) and set(users1) == set(users3)

    # Check if timestamps are updating
    before_updated = admin_user.updated
    before_indexed = admin_user.indexed
    with es.session.begin(blocking=True, forced=True):
        admin_user.index()
    after_updated = admin_user.updated
    after_indexed = admin_user.indexed

    assert before_updated <= before_indexed
    assert after_updated <= after_indexed
    assert before_updated <= after_updated
    assert before_indexed < after_indexed

    # Check if it updated if not forced
    before_updated = admin_user.updated
    before_indexed = admin_user.indexed
    with es.session.begin(blocking=True, forced=False):
        admin_user.index()
    after_updated = admin_user.updated
    after_indexed = admin_user.indexed

    assert before_updated <= before_indexed
    assert after_updated <= after_indexed
    assert before_updated == after_updated
    assert before_indexed == after_indexed

    # Check if it updated if forced, but ES is disabled
    before_updated = admin_user.updated
    before_indexed = admin_user.indexed
    es.off()
    with es.session.begin(blocking=True, forced=True):
        admin_user.index()
    es.on()
    after_updated = admin_user.updated
    after_indexed = admin_user.indexed

    assert before_updated <= before_indexed
    assert after_updated <= after_indexed
    assert before_updated == after_updated
    assert before_indexed == after_indexed

    # Delete object from ES manually
    admin_user.prune().get('result', None) == 'deleted'
    assert admin_user.prune() is None
    assert not admin_user.elasticsearchable
    assert not admin_user.available()

    # Test global indexing, invalidating, pruning
    with es.session.begin(blocking=True, forced=True, verify=True):
        es.es_index_all()
    with es.session.begin(blocking=True, forced=True, verify=True):
        es.es_invalidate_all()
    with es.session.begin(blocking=True, forced=True, verify=True):
        es.es_prune_all()

    with es.session.begin(blocking=False, forced=True, verify=True):
        es.es_index_all()
    with es.session.begin(blocking=False, forced=True, verify=True):
        es.es_invalidate_all()
    with es.session.begin(blocking=False, forced=True, verify=True):
        es.es_prune_all()

    # Assert empty
    users = User.elasticsearch(None, load=False)
    assert len(users) == 0

    # Check if we can get information out of a non-registered model
    cls = ComplexDateTime
    assert cls not in es.REGISTERED_MODELS

    with db.session.begin():
        cdt = cls(datetime.datetime.utcnow(), 'US/Pacific', Specificities.day)
        assert cdt
        db.session.add(cdt)

    assert es.es_index_name(cls) is None
    assert es.es_index(cdt) is None
    assert es.es_get(cdt) is None

    assert es.es_index_exists(index)
    assert len(es.es_index_mappings(index)) > 0
    assert es.es_refresh_index(index) is None
    assert es.es_delete_index(index)

    index = 'index.that.does.not.exist'
    assert not es.es_index_exists(index)
    assert es.es_index_mappings(index) is None
    assert es.es_refresh_index(index) is None
    assert es.es_delete_index(index) is None
    assert es.es_delete_guid(cls, cdt.guid) is None
    assert es.es_delete_guid(User, cdt.guid) is None  # wrong class for this GUID

    # Searching on a non-registered class should return an empty list
    app = flask_app_client.application
    assert len(es.elasticsearch_on_class(app, cls, {})) == 0
    try:
        es.es_serialize(cdt)
        raise RuntimeError()
    except AssertionError:
        # building the index body on a non-registered object should fail
        pass

    try:
        with es.session.begin():
            admin_user.index()
            raise RuntimeError()
    except RuntimeError:
        assert not es.session.in_bulk_mode()
        assert len(es.session.bulk_actions) == 0

    with es.session.begin(blocking=True, forced=True, verify=True):
        es.es_index_all()

    # Test tasks
    assert es_tasks.elasticsearch_refresh_index_all.s(True).apply().result
    assert es_tasks.elasticsearch_invalidate_indexed_timestamps.s(True).apply().result


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'), reason='Elasticsearch extension disabled'
)
def test_model_search(flask_app_client, staff_user):
    from app.extensions import elasticsearch as es
    from app.modules.users.models import User

    if es.is_disabled():
        return

    # Initial search to setup the oauth user
    elasticsearch(flask_app_client, staff_user, 'users')

    # Index all users
    with es.session.begin(blocking=True):
        User.index_all(force=True)

    # Wait for elasticsearch to catch up
    wait_for_elasticsearch_status(flask_app_client, staff_user)

    count = 0
    while True:
        count += 1
        if count > 10:
            raise RuntimeError()

        try:
            search = {}
            # Check that the API for a mission's collections agrees
            response = elasticsearch(flask_app_client, staff_user, 'users', search)
            users = User.query.all()
            assert len(response.json) == len(users)
            break
        except AssertionError:
            pass

        time.sleep(1)

    # filter users by searching
    search = {
        'bool': {
            'filter': [
                {
                    'query_string': {
                        'query': '*wildme*',
                        'fields': [
                            'email',
                            'full_name',
                        ],
                        'default_operator': 'OR',
                    },
                },
            ],
        },
    }
    response = elasticsearch(flask_app_client, staff_user, 'users', search)
    assert len(response.json) == 1

    # Check intentional error
    search = {
        'bool': {
            'filter': [
                {
                    'query_string': {
                        'query': '*wildme*',
                        'fields': [
                            'doesnotexist',
                        ],
                        'default_operator': 'OR',
                    },
                },
            ],
        },
    }
    response = elasticsearch(flask_app_client, staff_user, 'users', search)
    assert len(response.json) == 0

    # Check intentional error
    search = {
        'bool': {
            'filter': [
                {
                    'incorrect-syntax': {
                        'query': '*wildme*',
                        'fields': [
                            'doesnotexist',
                        ],
                        'default_operator': 'OR',
                    },
                },
            ],
        },
    }
    elasticsearch(flask_app_client, staff_user, 'users', search, expected_status_code=400)
