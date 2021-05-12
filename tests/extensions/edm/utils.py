# -*- coding: utf-8 -*-
"""
EDM utils
-------------
"""
import json
from tests import utils as test_utils

CONFIG_PATH = '/api/v1/configuration/default'


def configuration_post(
    flask_app_client,
    user,
    data_in={},
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('configuration:write',)):
        response = flask_app_client.post(
            CONFIG_PATH,
            data=json.dumps(data_in),
            content_type='application/json',
        )
    test_utils.validate_dict_response(response, expected_status_code, {'success'})
    assert response.json['success']
    return response


def custom_field_create(
    flask_app_client,
    user,
    name,
    cls='Occurrence',
    type='string',
    multiple=False,
):
    data = {
        'definitions': [
            {
                'name': name,
                'type': type,
                'multiple': multiple,
            }
        ]
    }
    payload = {}
    payload['site.custom.customFields.' + cls] = data
    response = configuration_post(flask_app_client, user, payload)
    assert response.json.get('success', False)
    cfd_list = response.json.get('updatedCustomFieldDefinitionIds', None)
    assert cfd_list
    return cfd_list[0]
