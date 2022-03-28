# -*- coding: utf-8 -*-
"""
Asset_group resources utils
-------------
"""

from tests import utils as test_utils
import json

PATH = '/api/v1/users/'


def create_user(
    flask_app_client, user, data, expected_status_code=200, expected_error=None
):
    return test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes='',
        path=PATH,
        data=data,
        response_200={'guid', 'email'},
        expected_status_code=expected_status_code,
        expected_error=expected_error,
    )


def read_user(flask_app_client, user, sub_path, expected_status_code=200):
    response = read_user_path(flask_app_client, user, sub_path, expected_status_code)
    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'guid', 'full_name', 'collaborations'}
        )
    return response


def read_user_path(flask_app_client, user, sub_path, expected_status_code=200):
    if user:
        with flask_app_client.login(user, auth_scopes=('users:read',)):
            response = flask_app_client.get(f'{PATH}{sub_path}')
    else:
        response = flask_app_client.get(f'{PATH}{sub_path}')
    if expected_status_code != 200:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_users_pagination(flask_app_client, user, expected_status_code=200, **kwargs):
    assert set(kwargs.keys()) <= {'limit', 'offset', 'sort', 'reverse', 'reverse_after'}

    with flask_app_client.login(user, auth_scopes=('users:read',)):
        response = flask_app_client.get(
            PATH,
            query_string=kwargs,
        )

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def patch_user(
    flask_app_client,
    running_user,
    user_modified,
    data,
    expected_status_code=200,
    expected_error='',
):
    with flask_app_client.login(running_user, auth_scopes=('users:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH, user_modified.guid),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
        assert response.json['message'] == expected_error, response.json['message']

    return response


def delete_user(flask_app_client, user, expected_status_code=204):
    test_utils.delete_via_flask(
        flask_app_client,
        user,
        scopes='users:write',
        path=f'{PATH}{user.guid}',
        expected_status_code=expected_status_code,
    )
