# -*- coding: utf-8 -*-
"""
Assets resources utils
-------------
"""
import json
from tests import utils as test_utils

PATH = '/api/v1/assets/'


def patch_asset(flask_app_client, asset_guid, user, data, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('assets:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH, asset_guid),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'submission', 'src', 'guid', 'filename'}
        )
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_asset(flask_app_client, user, asset_guid, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('assets:read',)):
        response = flask_app_client.get('%s%s' % (PATH, asset_guid))

    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'asset_group', 'src', 'guid', 'filename'}
        )
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_assets(flask_app_client, user, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('assets:read',)):
        response = flask_app_client.get(PATH)

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def delete_asset(flask_app_client, user, asset_guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('assets:write',)):
        response = flask_app_client.delete('%s%s' % (PATH, asset_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
