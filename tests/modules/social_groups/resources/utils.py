# -*- coding: utf-8 -*-
"""
social_group resources utils
-------------
"""
import json
from tests import utils as test_utils

PATH = '/api/v1/social-groups/'
SETTING_PATH = '/api/v1/site-settings/'
EXPECTED_KEYS = {'guid', 'name', 'members'}
EXPECTED_LIST_KEYS = {'guid'}
EXPECTED_SETTING_KEYS = {'key', 'string'}


def create_social_group(
    flask_app_client, user, data, expected_status_code=200, expected_error=''
):
    if user:
        with flask_app_client.login(user, auth_scopes=('social-groups:write',)):
            response = flask_app_client.post(
                PATH,
                content_type='application/json',
                data=json.dumps(data),
            )
    else:
        response = flask_app_client.post(
            PATH,
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, EXPECTED_KEYS)
    elif 400 <= expected_status_code < 500:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
        assert response.json['message'] == expected_error, response.json['message']
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def patch_social_group(
    flask_app_client,
    social_group_guid,
    user,
    data,
    expected_status_code=200,
    expected_error=None,
):
    return test_utils.patch_via_flask(
        flask_app_client,
        user,
        scopes='social-groups:write',
        path=f'{PATH}{social_group_guid}',
        data=data,
        expected_status_code=expected_status_code,
        response_200={'guid'},
        expected_error=expected_error,
    )


def read_social_group(
    flask_app_client, user, social_group_guid, expected_status_code=200
):
    return test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='social-groups:read',
        path=f'{PATH}{social_group_guid}',
        expected_status_code=expected_status_code,
        response_200=EXPECTED_KEYS,
    )


def read_all_social_groups(flask_app_client, user, expected_status_code=200):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='social-groups:read',
        path=PATH,
        expected_status_code=expected_status_code,
        expected_fields=EXPECTED_LIST_KEYS,
    )


def delete_social_group(
    flask_app_client, user, social_group_guid, expected_status_code=204
):
    return test_utils.delete_via_flask(
        flask_app_client,
        user,
        scopes='social-groups:write',
        path=f'{PATH}{social_group_guid}',
        expected_status_code=expected_status_code,
    )


def set_roles(
    flask_app_client,
    user,
    data,
    expected_status_code=200,
    expected_error=None,
):
    return test_utils.post_via_flask(
        flask_app_client,
        user,
        'site-settings:write',
        SETTING_PATH,
        data,
        expected_status_code,
        EXPECTED_SETTING_KEYS,
        expected_error,
    )


# expected to work so just have a simple util
def set_basic_roles(flask_app_client, user):
    data = {
        'key': 'social_group_roles',
        'string': json.dumps(
            {
                'Matriarch': {'multipleInGroup': False},
                'IrritatingGit': {'multipleInGroup': True},
            }
        ),
    }
    return set_roles(flask_app_client, user, data)


def get_roles(flask_app_client, user, expected_status_code=200, expected_error=None):
    return test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        'site-settings:read',
        f'{SETTING_PATH}social_group_roles',
        expected_status_code,
        EXPECTED_SETTING_KEYS,
        expected_error,
    )


def delete_roles(flask_app_client, user, expected_status_code=204, expected_error=None):
    return test_utils.delete_via_flask(
        flask_app_client,
        user,
        'site-settings:write',
        f'{SETTING_PATH}social_group_roles',
        expected_status_code,
        expected_error,
    )
