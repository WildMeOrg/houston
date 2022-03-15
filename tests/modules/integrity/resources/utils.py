# -*- coding: utf-8 -*-
"""
integrity resources utils
-------------
"""
from tests import utils as test_utils

PATH = '/api/v1/integrity-checks/'
EXPECTED_KEYS = {'guid', 'created', 'result'}


def create(
    flask_app_client,
    user,
    expected_status_code=200,
    expected_error='',
    request=None,
):
    resp = test_utils.post_via_flask(
        flask_app_client,
        user,
        'integrity:write',
        PATH,
        None,
        expected_status_code,
        EXPECTED_KEYS,
        expected_error,
    )
    if request:
        check_guid = resp.json['guid']
        request.addfinalizer(lambda: delete(flask_app_client, user, check_guid))
    return resp


def read(flask_app_client, user, guid, expected_status_code=200):
    return test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='integrity:read',
        path=f'{PATH}{guid}',
        expected_status_code=expected_status_code,
        response_200=EXPECTED_KEYS,
    )


def read_all(flask_app_client, user, expected_status_code=200):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='integrity:read',
        path=PATH,
        expected_status_code=expected_status_code,
        expected_fields=EXPECTED_KEYS,
    )


def delete(flask_app_client, user, guid, expected_status_code=204):
    return test_utils.delete_via_flask(
        flask_app_client,
        user,
        scopes='integrity:write',
        path=f'{PATH}{guid}',
        expected_status_code=expected_status_code,
    )
