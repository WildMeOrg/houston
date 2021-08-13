# -*- coding: utf-8 -*-
"""
Asset_group resources utils
-------------
"""

from tests import utils as test_utils

PATH = '/api/v1/users/'


def read_user(flask_app_client, user, sub_path, expected_status_code=200):
    if user:
        with flask_app_client.login(user, auth_scopes=('users:read',)):
            response = flask_app_client.get(f'{PATH}{sub_path}')
    else:
        response = flask_app_client.get(f'{PATH}{sub_path}')
    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'guid', 'full_name', 'collaborations'}
        )
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response
