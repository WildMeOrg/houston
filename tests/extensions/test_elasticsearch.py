# -*- coding: utf-8 -*-
import datetime
import time

import pytest
import tqdm

from tests.utils import (
    elasticsearch,
    extension_unavailable,
    module_unavailable,
    wait_for_elasticsearch_status,
)


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'), reason='Elasticsearch extension disabled'
)
def test_indexing_with_elasticsearch():
    from app.extensions import elasticsearch as es
    from app.modules.assets.models import AssetTags
    from app.modules.users.models import User

    assert User in es.REGISTERED_MODELS
    assert AssetTags not in es.REGISTERED_MODELS

    User.index_all()
    AssetTags.index_all()


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension or module disabled',
)
def test_index_cls_conversion():
    from app.extensions import elasticsearch as es
    from app.modules.users.models import User

    index = es.es_index_name(User)
    cls = es.es_index_class(index)

    if None in [index, cls]:
        assert index is None
        assert cls is None
        assert es.is_disabled()
    else:
        assert es.is_enabled()
        assert cls == User


@pytest.mark.skipif(
    extension_unavailable('elasticsearch') or module_unavailable('asset_groups'),
    reason='Elasticsearch extension or module disabled, or Asset Groups module is disabled',
)
def test_elasticsearch_utilities(
    flask_app_client,
    db,
    admin_user,
    staff_user,
    readonly_user,
    user_manager_user,
    regular_user,
    internal_user,
    temp_user,
    collab_user_a,
    collab_user_b,
    request,
    test_root,
):
    import tests.modules.asset_groups.resources.utils as asset_group_utils
    from app.extensions import elasticsearch as es
    from app.extensions.elasticsearch import tasks as es_tasks
    from app.modules.assets.models import Asset
    from app.modules.complex_date_time.models import ComplexDateTime, Specificities
    from app.modules.users.models import User
    from app.modules.users.schemas import UserListSchema
    from tests.modules.assets.resources.utils import read_all_assets_pagination
    from tests.modules.users.resources.utils import read_all_users_pagination

    if es.is_disabled():
        pytest.skip('Elasticsearch disabled (via command-line)')

    body = {}

    es.check_celery(revoke=True)
    es.es_checkpoint()
    assert len(es.es_status(outdated=False, health=False)) == 0
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

    data = es.es_serialize(admin_user)
    data2 = admin_user.serialize()
    data[-1].pop('indexed')
    data2[-1].pop('indexed')
    assert data == data2
    index, guid, body_schema = data
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

    with es.session.begin(blocking=True):
        assert admin_user.index() == 'tracked'
    assert admin_user.fetch().get('found', True)
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

    total1, users1 = User.elasticsearch(body, total=True, load=False)
    assert total1 >= len(users1)
    assert len(users1) <= 100

    # Check refresh and search
    es.es_refresh_index(es.es_index_name(User))

    total2, users2 = User.elasticsearch(body, total=True, load=False)
    assert total1 == total2
    assert users1 == users2

    # Check if we can prune objects
    with es.session.begin(blocking=True):
        User.prune_all()
    es.es_checkpoint()

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

    es.es_checkpoint()

    # Test sorting
    users = User.elasticsearch(body)
    vals = [user.guid for user in users]
    assert vals == sorted(vals)
    users = User.elasticsearch(body, sort='indexed')
    vals = [user.indexed for user in users]
    assert vals == sorted(vals)
    users = User.elasticsearch(body, sort='indexed', reverse=True)
    vals = [user.indexed for user in users]
    assert vals == sorted(vals, reverse=True)

    _, users = User.elasticsearch(body, total=True)
    vals = [user.guid for user in users]
    assert vals == sorted(vals)
    _, users = User.elasticsearch(body, total=True, sort='indexed')
    vals = [user.indexed for user in users]
    assert vals == sorted(vals)
    _, users = User.elasticsearch(body, total=True, sort='indexed', reverse=True)
    vals = [user.indexed for user in users]
    assert vals == sorted(vals, reverse=True)

    # Test indexing
    total1, users1 = User.elasticsearch(body, total=True, sort='guid')
    total2, users2 = User.elasticsearch(body, total=True, sort='indexed')
    total3, users3 = User.elasticsearch(body, total=True, sort='indexed', reverse=True)

    vals2 = [user.indexed for user in users2]
    assert vals2 == sorted(vals2)
    vals3 = [user.indexed for user in users3]
    assert vals3 == sorted(vals3, reverse=True)
    assert vals2 == vals3[::-1]
    assert total1 == total2 and total2 == total3
    assert set(users1) == set(users2) and set(users1) == set(users3)

    with es.session.begin(blocking=True, forced=True):
        es.es_index_mappings_patch(User)
    with es.session.begin(blocking=True, forced=True):
        User.index_all()

    # Check pagination
    reference = User.elasticsearch(body)

    # Build all possible configurations
    configs = []
    for load in [True, False]:
        for total in [True, False]:
            for limit in [None, 1, 5, 100]:
                for offset in [None, 0, 5, 100]:
                    for sort in [
                        None,
                        'guid',
                        'indexed',
                        # 'full_name',
                        'elasticsearch.guid',
                    ]:
                        for reverse in [True, False]:
                            for reverse_after in [True, False]:
                                config = (
                                    load,
                                    total,
                                    limit,
                                    offset,
                                    sort,
                                    reverse,
                                    reverse_after,
                                )
                                configs.append(config)

    # Test pagination for Elasticsearch
    failures = []
    for config in tqdm.tqdm(configs):
        load, total, limit, offset, sort, reverse, reverse_after = config
        config_str = (
            'load=%r, total=%r, limit=%r, offset=%r, sort=%r, reverse=%r, reverse_after=%r'
            % config
        )
        print(config_str)
        try:
            kwargs = {
                'load': load,
                'total': total,
                'reverse': reverse,
                'reverse_after': reverse_after,
            }
            if limit is not None:
                kwargs['limit'] = limit
            if offset is not None:
                kwargs['offset'] = offset
            if sort is not None:
                kwargs['sort'] = sort

            results = User.elasticsearch(body, **kwargs)

            if total:
                total_, users = results
                assert total_ == len(reference)
            else:
                users = results

            compare = reference[:]

            if sort in [None, 'guid']:
                compare.sort(key=lambda user: user.guid, reverse=reverse)
            elif sort == 'indexed':
                compare.sort(key=lambda user: (user.indexed, user.guid), reverse=reverse)
            # elif sort == 'full_name':
            #     compare.sort(
            #         key=lambda user: (user.full_name, user.guid), reverse=reverse
            #     )
            elif sort == 'elasticsearch.guid':
                values = []
                for user in compare:
                    es_guid = user.fetch().get('_source', {}).get('guid')
                    values.append((es_guid, user))
                values.sort(reverse=reverse)
                compare = [value[1] for value in values]
            else:
                raise ValueError()

            if offset is not None:
                compare = compare[offset:]
            if limit is not None:
                compare = compare[:limit]

            if reverse_after:
                compare = compare[::-1]

            if not load:
                compare = [user.guid for user in compare]

            assert users == compare
        except AssertionError:
            failures.append(config_str)

    print(failures)
    assert len(failures) == 0

    # Build all possible configurations
    configs = []
    for limit in [None, 1, 5, 100]:
        for offset in [None, 0, 5, 100]:
            for sort in [None, 'guid', 'indexed', 'elasticsearch.guid']:
                for reverse in [True, False]:
                    for reverse_after in [True, False]:
                        config = (limit, offset, sort, reverse, reverse_after)
                        configs.append(config)

    # Make one request to ensure the oauth user has been createda
    response = read_all_users_pagination(flask_app_client, staff_user)

    # Check pagination
    reference = User.query.all()

    # Test pagination for listing APIs
    failures = []
    for config in tqdm.tqdm(configs):
        limit, offset, sort, reverse, reverse_after = config
        config_str = 'limit=%r, offset=%r, sort=%r, reverse=%r, reverse_after=%r' % config
        print(config_str)
        try:
            kwargs = {
                'reverse': reverse,
                'reverse_after': reverse_after,
            }
            if limit is not None:
                kwargs['limit'] = limit
            if offset is not None:
                kwargs['offset'] = offset
            if sort is not None:
                kwargs['sort'] = sort
            response = read_all_users_pagination(flask_app_client, staff_user, **kwargs)

            users = response.json
            users = [user['guid'] for user in users]

            compare = reference[:]

            if sort in [None, 'guid', 'elasticsearch.guid']:
                compare.sort(key=lambda user: user.guid, reverse=reverse)
            elif sort == 'indexed':
                compare.sort(key=lambda user: (user.indexed, user.guid), reverse=reverse)
            # elif sort == 'full_name':
            #     compare.sort(
            #         key=lambda user: (user.full_name, user.guid), reverse=reverse
            #     )
            else:
                raise ValueError()

            if offset is not None:
                compare = compare[offset:]
            if limit is not None:
                compare = compare[:limit]

            if reverse_after:
                compare = compare[::-1]

            compare = [str(user.guid) for user in compare]

            assert users == compare
        except AssertionError:
            failures.append(config_str)

    asset_group_utils.create_simple_asset_group_uuids(
        flask_app_client, staff_user, request, test_root
    )

    with es.session.begin(blocking=True, verify=True):
        Asset.index_all()

    es.es_checkpoint()

    # Check pagination
    reference = Asset.elasticsearch(body)

    # Build all possible configurations
    configs = []
    for load in [True, False]:
        for total in [True, False]:
            for limit in [None, 1, 10]:
                for offset in [None, 0, 1, 10]:
                    for sort in [
                        None,
                        'magic_signature',
                        'path',
                        'elasticsearch.annotation_count',
                    ]:
                        for reverse in [True, False]:
                            for reverse_after in [True, False]:
                                config = (
                                    load,
                                    total,
                                    limit,
                                    offset,
                                    sort,
                                    reverse,
                                    reverse_after,
                                )
                                configs.append(config)

    # Test pagination for Elasticsearch
    failures = []
    for config in tqdm.tqdm(configs):
        load, total, limit, offset, sort, reverse, reverse_after = config
        config_str = (
            'load=%r, total=%r, limit=%r, offset=%r, sort=%r, reverse=%r, reverse_after=%r'
            % config
        )
        print(config_str)
        try:
            kwargs = {
                'load': load,
                'total': total,
                'reverse': reverse,
                'reverse_after': reverse_after,
            }
            if limit is not None:
                kwargs['limit'] = limit
            if offset is not None:
                kwargs['offset'] = offset
            if sort is not None:
                kwargs['sort'] = sort

            results = Asset.elasticsearch(body, **kwargs)

            if total:
                total_, assets = results
                assert total_ == len(reference)
            else:
                assets = results

            compare = reference[:]

            if sort in [None, 'guid']:
                compare.sort(key=lambda asset: asset.guid, reverse=reverse)
            elif sort == 'magic_signature':
                compare.sort(
                    key=lambda asset: (asset.magic_signature, asset.guid), reverse=reverse
                )
            elif sort == 'path':
                compare.sort(key=lambda asset: (asset.path, asset.guid), reverse=reverse)
            elif sort == 'elasticsearch.annotation_count':
                values = []
                for asset in compare:
                    es_guid = asset.fetch().get('_source', {}).get('annotation_count')
                    values.append((es_guid, asset))
                values.sort(reverse=reverse)
                compare = [value[1] for value in values]
            else:
                raise ValueError()

            if offset is not None:
                compare = compare[offset:]
            if limit is not None:
                compare = compare[:limit]

            if reverse_after:
                compare = compare[::-1]

            if not load:
                compare = [asset.guid for asset in compare]

            assert assets == compare
        except AssertionError:
            failures.append(config_str)

    print(failures)
    assert len(failures) == 0

    # Build all possible configurations
    configs = []
    for limit in [None, 1, 10]:
        for offset in [None, 0, 1, 10]:
            for sort in [
                None,
                'magic_signature',
                'path',
                'elasticsearch.annotation_count',
            ]:
                for reverse in [True, False]:
                    for reverse_after in [True, False]:
                        config = (limit, offset, sort, reverse, reverse_after)
                        configs.append(config)

    # Make one request to ensure the oauth user has been createda
    response = read_all_assets_pagination(flask_app_client, staff_user)

    # Check pagination
    reference = Asset.query.all()

    # Test pagination for listing APIs
    failures = []
    for config in tqdm.tqdm(configs):
        limit, offset, sort, reverse, reverse_after = config
        config_str = 'limit=%r, offset=%r, sort=%r, reverse=%r, reverse_after=%r' % config
        print(config_str)
        try:
            kwargs = {
                'reverse': reverse,
                'reverse_after': reverse_after,
            }
            if limit is not None:
                kwargs['limit'] = limit
            if offset is not None:
                kwargs['offset'] = offset
            if sort is not None:
                kwargs['sort'] = sort
            response = read_all_assets_pagination(flask_app_client, staff_user, **kwargs)

            assets = response.json
            assets = [asset['guid'] for asset in assets]

            compare = reference[:]

            if sort in [None, 'guid', 'elasticsearch.annotation_count']:
                compare.sort(key=lambda asset: asset.guid, reverse=reverse)
            elif sort == 'magic_signature':
                compare.sort(
                    key=lambda asset: (asset.magic_signature, asset.guid), reverse=reverse
                )
            elif sort == 'path':
                compare.sort(key=lambda asset: (asset.path, asset.guid), reverse=reverse)
            else:
                raise ValueError()

            if offset is not None:
                compare = compare[offset:]
            if limit is not None:
                compare = compare[:limit]

            if reverse_after:
                compare = compare[::-1]

            compare = [str(asset.guid) for asset in compare]

            assert assets == compare
        except AssertionError:
            failures.append(config_str)

    print(failures)
    assert len(failures) == 0

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
    with es.session.begin(blocking=True, forced=True):
        es.es_index_all()
    with es.session.begin(blocking=True, forced=True):
        es.es_invalidate_all()
    with es.session.begin(blocking=True, forced=True):
        es.es_prune_all()

    with es.session.begin(blocking=False, forced=True):
        es.es_index_all()
    with es.session.begin(blocking=False, forced=True):
        es.es_invalidate_all()
    with es.session.begin(blocking=False, forced=True):
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
    assert len(es.es_elasticsearch(app, cls, body)) == 0
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
    es_tasks.es_task_refresh_index_all(True)
    es_tasks.es_task_invalidate_indexed_timestamps(True)


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension or module disabled',
)
def test_model_search(flask_app_client, staff_user):
    from app.extensions import elasticsearch as es
    from app.modules.users.models import User

    if es.is_disabled():
        pytest.skip('Elasticsearch disabled (via command-line)')

    wait_for_elasticsearch_status(flask_app_client, staff_user)

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
