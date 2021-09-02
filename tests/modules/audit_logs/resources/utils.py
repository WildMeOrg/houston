# -*- coding: utf-8 -*-
"""
audit_log resources utils
-------------
"""
from tests import utils as test_utils

PATH = '/api/v1/audit_logs/'


def read_audit_log(flask_app_client, user, audit_log_guid, expected_status_code=200):
    if user:
        with flask_app_client.login(user, auth_scopes=('audit_logs:read',)):
            response = flask_app_client.get(f'{PATH}{audit_log_guid}')
    else:
        response = flask_app_client.get(f'{PATH}{audit_log_guid}')

    expected_keys = {'item_guid', 'module_name', 'message', 'user_email'}

    if expected_status_code == 200:
        test_utils.validate_list_of_dictionaries_response(response, 200, expected_keys)
    elif expected_status_code == 404:
        test_utils.validate_dict_response(response, expected_status_code, {'message'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_audit_logs(
    flask_app_client, user, expected_status_code=200, module_name=None
):
    with flask_app_client.login(user, auth_scopes=('audit_logs:read',)):
        query = {'limit': 30}
        if module_name:
            query['module_name'] = module_name
        response = flask_app_client.get(PATH, query_string=query)
    expected_keys = {'item_guid', 'module_name'}
    if expected_status_code == 200:
        test_utils.validate_list_of_dictionaries_response(response, 200, expected_keys)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response
