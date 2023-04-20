# -*- coding: utf-8 -*-
"""
Individual resources utils
-------------
"""
import json
import logging

from tests import utils as test_utils
from tests.modules.sightings.resources import utils as sighting_utils

PATH = '/api/v1/individuals/'
EXPECTED_KEYS = {
    'names',
    'timeOfBirth',
    'social_groups',
    'hasView',
    'hasEdit',
    'timeOfDeath',
    'customFields',
    'guid',
    'featuredAssetGuid',
    'encounters',
    'comments',
}
log = logging.getLogger(__name__)  # pylint: disable=invalid-name


# Caller must populate the encounter info in the data in
def create_individual(flask_app_client, user, expected_status_code=200, data_in={}):

    if not data_in.get('taxonomy'):
        from tests.modules.site_settings.resources import utils as setting_utils

        taxonomy = setting_utils.get_some_taxonomy_dict(flask_app_client, user)
        data_in['taxonomy'] = taxonomy['id']

    with flask_app_client.login(user, auth_scopes=('individuals:write',)):
        response = flask_app_client.post(
            PATH,
            data=json.dumps(data_in),
            content_type='application/json',
        )

    assert isinstance(response.json, dict)
    assert response.status_code == expected_status_code, response.status_code
    if response.status_code == 200:
        test_utils.validate_dict_response(response, 200, EXPECTED_KEYS)

    return response


# Encounter info not populate in individual_data by caller, this helper creates a sighting with one encounter
# and then creates the individual in the encounter created
def create_individual_and_sighting(
    flask_app_client,
    owner_user,
    request,
    test_root,
    sighting_data=None,
    individual_data=None,
    large=False,
    researcher_user=None,
):
    if large:
        # large means this test wants the specific large sighting data, to set specific data, use non large
        assert sighting_data is None
        uuids = sighting_utils.create_large_sighting(
            flask_app_client, owner_user, request, test_root, researcher_user
        )
    else:
        uuids = sighting_utils.create_sighting(
            flask_app_client,
            owner_user,
            request,
            test_root,
            sighting_data,
            commit_user=researcher_user,
        )

    if not researcher_user:
        researcher_user = owner_user

    # Extract the encounters to use to create an individual
    assert len(uuids['encounters']) >= 1
    if individual_data:
        individual_data['encounters'] = [{'id': uuids['encounters'][0]}]
    else:
        individual_data = {'encounters': [{'id': uuids['encounters'][0]}]}

    individual_response = create_individual(
        flask_app_client, researcher_user, 200, individual_data
    )

    individual_guid = individual_response.json['guid']
    request.addfinalizer(
        lambda: delete_individual(flask_app_client, researcher_user, individual_guid)
    )
    uuids['individual'] = individual_guid

    return uuids


def read_individual(
    flask_app_client, regular_user, individual_guid, expected_status_code=200
):
    with flask_app_client.login(regular_user, auth_scopes=('individuals:read',)):
        response = flask_app_client.get('{}{}'.format(PATH, individual_guid))

    assert response.status_code == expected_status_code
    if response.status_code == 200:
        test_utils.validate_dict_response(response, 200, EXPECTED_KEYS)
    return response


# As above but does not assume any format output, can be used for sub paths
def read_individual_path(
    flask_app_client, regular_user, individual_path, expected_status_code=200
):
    with flask_app_client.login(regular_user, auth_scopes=('individuals:read',)):
        response = flask_app_client.get(f'{PATH}{individual_path}')
    assert response.status_code == expected_status_code
    return response


def delete_individual(flask_app_client, user, guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('individuals:write',)):
        response = flask_app_client.delete('{}{}'.format(PATH, guid))

    if expected_status_code == 204:
        # we allow 404 here in the event that it is being called as a finalizer on an
        #   individual which was deleted by the test (e.g. during merges)
        assert (
            response.status_code == 204 or response.status_code == 404
        ), response.status_code
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )


def patch_individual(
    flask_app_client,
    user,
    individual_guid,
    patch_data=[],
    headers=None,
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('individuals:write',)):
        response = flask_app_client.patch(
            '{}{}'.format(PATH, individual_guid),
            data=json.dumps(patch_data),
            content_type='application/json',
            headers=headers,
        )

    assert isinstance(response.json, dict)
    assert response.status_code == expected_status_code, response
    return response


def merge_individuals(
    flask_app_client,
    user,
    individual_id,
    data_in,
    auth_scopes=('individuals:write',),
    expected_status_code=200,
    expected_fields={'merged'},
):
    resp = test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes=auth_scopes,
        path=f'/api/v1/individuals/{individual_id}/merge',
        data=data_in,
        expected_status_code=expected_status_code,
        response_200=expected_fields,
    )
    return resp.json


def get_merge_request(
    flask_app_client,
    user,
    request_id,
    auth_scopes=('individuals:write',),
    expected_status_code=200,
):
    resp = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes=auth_scopes,
        path=f'/api/v1/individuals/merge_request/{request_id}',
        expected_status_code=expected_status_code,
        response_200=set(),
    )
    return resp


def vote_merge_request(
    flask_app_client,
    user,
    request_id,
    vote,
    auth_scopes=('individuals:write',),
    expected_status_code=200,
):
    resp = test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes=auth_scopes,
        path=f'/api/v1/individuals/merge_request/{request_id}',
        data={'vote': vote},
        expected_status_code=expected_status_code,
        response_200=set(),
    )
    return resp


def merge_conflicts(
    flask_app_client,
    user,
    individuals,
    auth_scopes=('individuals:write',),
    expected_status_code=200,
):
    resp = test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes=auth_scopes,
        path='/api/v1/individuals/merge_conflict_check',
        data=individuals,
        expected_status_code=expected_status_code,
        response_200=set(),
    )
    return resp.json


def validate_names(
    flask_app_client,
    user,
    names_flatfile,
    auth_scopes=('individuals:read',),
    expected_status_code=200,
):
    resp = test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes=auth_scopes,
        path='/api/v1/individuals/validate',
        data=names_flatfile,
        expected_status_code=expected_status_code,
        response_200=set(),
        returns_list=True,
    )
    return resp
