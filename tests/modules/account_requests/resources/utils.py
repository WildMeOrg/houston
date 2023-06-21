# -*- coding: utf-8 -*-
"""
account_request resources utils
-------------
"""
from tests import utils as test_utils

PATH = '/api/v1/account-requests/'
EXPECTED_KEYS = {'guid', 'name', 'email', 'message'}


def create_account_request(
    flask_app_client,
    data,
    expected_status_code=200,
    expected_error='',
    request=None,
):
    resp = test_utils.post_via_flask(
        flask_app_client,
        None,
        None,
        PATH,
        data,
        expected_status_code,
        EXPECTED_KEYS,
        expected_error,
    )
    return resp


def read_all_account_requests(flask_app_client, user, expected_status_code=200):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='account_requests:read',
        path=PATH,
        expected_status_code=expected_status_code,
    )
