# -*- coding: utf-8 -*-
"""
Project resources utils
-------------
"""
from tests import utils as test_utils

PATH = '/api/v1/encounters/'

EXPECTED_FIELDS = {
    'hasView',
    'hasEdit',
    'guid',
    'owner',
    'updated',
    'annotations',
    'created',
    'submitter',
}


# to create an encounter, it must be part of a sighting, so we piggyback on sighting_util
def create_encounter(
    flask_app_client, user, request, test_root, expected_status_code=200
):
    from tests.modules.sightings.resources import utils as sighting_utils

    # Return is a map of the uuids of things created
    return sighting_utils.create_sighting(
        flask_app_client,
        user,
        request,
        test_root,
        expected_status_code=expected_status_code,
    )


def patch_encounter(
    flask_app_client,
    encounter_guid,
    user,
    data,
    expected_status_code=200,
    expected_error=None,
):
    response = test_utils.patch_via_flask(
        flask_app_client,
        user,
        'encounters:write',
        f'{PATH}{encounter_guid}',
        data,
        expected_status_code,
        response_200=EXPECTED_FIELDS,
        expected_error=expected_error,
    )
    if expected_status_code == 200:
        assert response.json['guid'] == str(encounter_guid)

    return response


def read_encounter(flask_app_client, user, enc_guid, expected_status_code=200):
    response = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        'encounters:read',
        f'{PATH}{enc_guid}',
        expected_status_code,
        response_200=EXPECTED_FIELDS,
    )

    if expected_status_code == 200:
        assert response.json['guid'] == str(enc_guid)
    return response


def read_all_encounters_pagination(
    flask_app_client, user, expected_status_code=200, **kwargs
):
    assert set(kwargs.keys()) <= {'limit', 'offset', 'sort', 'reverse', 'reverse_after'}

    with flask_app_client.login(user, auth_scopes=('encounters:read',)):
        response = flask_app_client.get(
            PATH,
            query_string=kwargs,
        )

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


# This returns a sighting debug object so acn't reuse above method as expected fields are way different
def read_encounter_debug(flask_app_client, user, enc_guid, expected_status_code=200):
    response = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        'encounters:read',
        f'{PATH}debug/{enc_guid}',
        expected_status_code,
        response_200={'guid'},
    )

    return response


def delete_encounter(
    flask_app_client, user, enc_guid, expected_status_code=204, headers=None
):
    with flask_app_client.login(user, auth_scopes=('encounter:write',)):
        response = flask_app_client.delete('{}{}'.format(PATH, enc_guid), headers=headers)

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response
