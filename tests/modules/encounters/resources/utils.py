# -*- coding: utf-8 -*-
"""
Project resources utils
-------------
"""
from tests import utils as test_utils

PATH = '/api/v1/encounters/'


# to create an encounter, it must be part of a sighting, so we piggyback on sighting_util
def create_encounter(flask_app_client, user, expected_status_code=200):
    from tests.modules.sightings.resources import utils as sighting_utils

    data_in = {
        'locationId': 'PYTEST-SIGHTING',
        'context': 'TEXT',
        'encounters': [{'locationId': 'PYTEST-ENCOUNTER'}],
    }
    response = sighting_utils.create_sighting(flask_app_client, user, data_in)
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
