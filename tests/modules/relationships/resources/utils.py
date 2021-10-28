# -*- coding: utf-8 -*-
"""
Relationship resources utils
-------------
"""
import logging
import json
from tests import utils as test_utils

PATH = '/api/v1/relationships/'

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


def create_relationship(flask_app_client, user, expected_status_code=200, data_in={}):
    with flask_app_client.login(user, auth_scopes=('relationships:write',)):
        response = flask_app_client.post(
            PATH,
            data=json.dumps(data_in),
            content_type='application/json',
        )

    assert isinstance(response.json, dict)
    assert response.status_code == expected_status_code
    if response.status_code == 200:
        test_utils.validate_dict_response(response, 200, {'success', 'result'})

    return response


def read_relationship(
    flask_app_client, regular_user, relationship_guid, expected_status_code=200
):
    with flask_app_client.login(regular_user, auth_scopes=('relationships:read',)):
        response = flask_app_client.get('%s%s' % (PATH, relationship_guid))

    assert response.status_code == expected_status_code
    if response.status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'guid', 'individuals', 'start_date', 'end_date', 'type'}
        )
    return response


def delete_relationship(
    flask_app_client, user, relationship_guid, expected_status_code=204
):
    with flask_app_client.login(user, auth_scopes=('relationships:write',)):
        response = flask_app_client.delete('%s%s' % (PATH, relationship_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )


def patch_relationship(
    flask_app_client,
    user,
    relationship_guid,
    patch_data=[],
    headers=None,
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('relationships:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH, relationship_guid),
            data=json.dumps(patch_data),
            content_type='application/json',
            headers=headers,
        )

    assert isinstance(response.json, dict)
    assert response.status_code == expected_status_code
    return response
