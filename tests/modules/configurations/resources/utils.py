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
    return test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='configuration:read',
        path=f'{CONFIG_PATH}/{conf_key}',
        expected_status_code=expected_status_code,
        response_200=EXPECTED_KEYS,
        response_error={'success', 'message'},
    )


def read_configuration_definition(
    flask_app_client,
    user,
    conf_key,
    expected_status_code=200,
):
    return test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='configuration:read',
        path=f'{CONFIG_DEF_PATH}/{conf_key}',
        expected_status_code=expected_status_code,
        response_200=EXPECTED_KEYS,
    )


def modify_configuration(
    flask_app_client,
    user,
    conf_key,
    data,
    expected_status_code=200,
):
    return test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes='configuration:write',
        path=f'{CONFIG_PATH}/{conf_key}',
        data=data,
        expected_status_code=expected_status_code,
        response_200={'success'},
    )
