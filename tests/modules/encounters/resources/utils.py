# -*- coding: utf-8 -*-
"""
Project resources utils
-------------
"""
import json
from tests import utils as test_utils

PATH = '/api/v1/encounters/'


def create_encounter(flask_app_client, user, expected_status_code=200):
    if user is not None:
        with flask_app_client.login(user):
            response = flask_app_client.post(
                PATH,
                data=json.dumps({'locationId': 'PYTEST'}),
                content_type='application/json',
            )
    else:
        response = flask_app_client.post(
            PATH,
            data=json.dumps({'locationId': 'PYTEST'}),
            content_type='application/json',
        )

    assert isinstance(response.json, dict)
    assert response.status_code == expected_status_code
    return response


def read_encounter(flask_app_client, user, enc_guid, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('encounters:read',)):
        response = flask_app_client.get('%s%s' % (PATH, enc_guid))

    assert isinstance(response.json, dict)
    assert response.status_code == expected_status_code
    if expected_status_code == 200:
        assert response.json['id'] == str(enc_guid)
    return response


def delete_encounter(flask_app_client, user, enc_guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('encounter:write',)):
        response = flask_app_client.delete('%s%s' % (PATH, enc_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
