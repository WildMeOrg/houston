# -*- coding: utf-8 -*-
"""
Configuration resources utils
-------------
"""
from tests import utils as test_utils

EXPECTED_KEYS = {'response', 'success'}
CONFIG_PATH = '/api/v1/configuration/default'
CONFIG_DEF_PATH = '/api/v1/configurationDefinition/default'


def read_configuration(
    flask_app_client,
    user,
    conf_key,
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('configuration:read',)):
        response = flask_app_client.get(
            f'{CONFIG_PATH}/{conf_key}',
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, EXPECTED_KEYS)
        assert response.json['success']
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'success', 'message'}
        )
    return response


def read_configuration_definition(
    flask_app_client,
    user,
    conf_key,
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('configuration:write',)):
        response = flask_app_client.get(
            f'{CONFIG_DEF_PATH}/{conf_key}',
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, EXPECTED_KEYS)
        assert response.json['success']
    else:
        test_utils.validate_dict_response(response, expected_status_code, EXPECTED_KEYS)
    return response


def modify_configuration(
    flask_app_client,
    user,
    conf_key,
    data,
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('annotations:write',)):
        response = flask_app_client.post(
            CONFIG_PATH, content_type='application/json', data=data
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, EXPECTED_KEYS)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response
