# -*- coding: utf-8 -*-
"""
social_group resources utils
-------------
"""
from tests import utils as test_utils

PATH = '/api/v1/social-groups/'
SETTING_PATH = '/api/v1/site-settings/'
EXPECTED_KEYS = {'guid', 'name', 'members'}
EXPECTED_LIST_KEYS = {'guid'}
EXPECTED_SETTING_KEYS = {'key', 'string'}


def create_social_group(
    flask_app_client,
    user,
    data,
    expected_status_code=200,
    expected_error='',
    request=None,
):
    resp = test_utils.post_via_flask(
        flask_app_client,
        user,
        'social-groups:write',
        PATH,
        data,
        expected_status_code,
        EXPECTED_KEYS,
        expected_error,
    )
    if request:
        group_guid = resp.json['guid']
        request.addfinalizer(
            lambda: delete_social_group(flask_app_client, user, group_guid)
        )
    return resp


def patch_social_group(
    flask_app_client,
    user,
    social_group_guid,
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
def set_basic_roles(flask_app_client, user, request):
    data = {
        'key': 'social_group_roles',
        'data': {
            'Matriarch': {'multipleInGroup': False},
            'IrritatingGit': {'multipleInGroup': True},
        },
    }
    resp = set_roles(flask_app_client, user, data)
    request.addfinalizer(lambda: delete_roles(flask_app_client, user))
    return resp


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


def validate_members(requested_members, response_members):

    for member_guid in requested_members:
        assert member_guid in response_members
        if 'roles' in requested_members[member_guid]:
            assert (
                response_members[member_guid]['roles']
                == requested_members[member_guid]['roles']
            )
        else:
            assert response_members[member_guid]['roles'] is None


def validate_response(request, response_json):
    assert response_json['name'] == request['name']
    validate_members(request['members'], response_json['members'])
