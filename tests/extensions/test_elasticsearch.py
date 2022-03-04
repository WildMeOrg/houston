# -*- coding: utf-8 -*-
import pytest
import time

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

    index = es.get_elasticsearch_index_name(User)
    cls = es.get_elasticsearch_cls_from_index(index)
    assert cls == User


@pytest.mark.skipif(
    extension_unavailable('elasticsearch'), reason='Elasticsearch extension disabled'
)
def test_model_search(flask_app_client, staff_user):
    from app.extensions import elasticsearch as es
    from app.modules.users.models import User

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
