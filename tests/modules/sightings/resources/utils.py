# -*- coding: utf-8 -*-
"""
Project resources utils
-------------
"""
import json
import uuid

from tests import utils as test_utils
import tests.extensions.tus.utils as tus_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils

PATH = '/api/v1/sightings/'

EXPECTED_FIELDS = {
    'curation_start_time',
    'created',
    'hasEdit',
    'review_time',
    'version',
    'createdHouston',
    'detection_start_time',
    'locationId',
    'comments',
    'hasView',
    'encounterCounts',
    'stage',
    'customFields',
    'createdEDM',
    'creator',
    'updated',
    'updatedHouston',
    'time',
    'timeSpecificity',
    'guid',
    'identification_start_time',
    'encounters',
    'unreviewed_start_time',
    'assets',
    'featuredAssetGuid',
}


# note: default data_in will fail
def create_old_sighting(
    flask_app_client,
    user,
    data_in={
        'locationId': 'PYTEST',
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
    },
    expected_status_code=200,
    expected_error=None,
):
    response = test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes='',
        path=PATH,
        data=data_in,
        expected_status_code=expected_status_code,
        response_200={'success'},
    )

    if expected_status_code == 200:
        assert response.json['success']
    else:
        assert response.json['message'] == expected_error

    return response


def create_sighting(
    flask_app_client,
    user,
    request,
    test_root,
    sighting_data=None,
    expected_status_code=200,
    expected_error=None,
    commit_expected_status_code=200,
):

    if not sighting_data:
        # Create a valid but simple one
        sighting_data = {
            'encounters': [{}],
            'time': '2000-01-01T01:01:01+00:00',
            'timeSpecificity': 'time',
            'locationId': 'test',
        }
    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    uuids = {'transaction': transaction_id}
    group_data = {
        'description': 'This is a test asset_group, please ignore',
        'uploadType': 'form',
        'speciesDetectionModel': [
            'None',
        ],
        'transactionId': transaction_id,
        'sightings': [
            sighting_data,
        ],
    }

    # Need to add the new filename to the sighting for the Asset group code to process it
    if 'assetReferences' not in group_data['sightings'][0].keys():
        group_data['sightings'][0]['assetReferences'] = []
    if test_filename not in group_data['sightings'][0]['assetReferences']:
        group_data['sightings'][0]['assetReferences'].append(test_filename)

    # For multiple encounters, it must be a bulk upload
    if 'encounters' in sighting_data and len(sighting_data['encounters']) > 1:
        group_data['uploadType'] = 'bulk'

    # Use shared helper to create the asset group and extract the uuids
    asset_group_uuids = _create_asset_group_extract_uuids(
        flask_app_client,
        user,
        group_data,
        request,
        expected_status_code,
        expected_error,
    )
    uuids.update(asset_group_uuids)

    # Shared helper to extract the sighting data
    if 'asset_group_sighting' in uuids.keys():
        sighting_uuids = _commit_sighting_extract_uuids(
            flask_app_client,
            user,
            uuids['asset_group_sighting'],
            expected_status_code=commit_expected_status_code,
        )
        if sighting_uuids:  # empty if non-200 above
            uuids.update(sighting_uuids)

    return uuids


# Helper that does what the above method does but for multiple files and multiple encounters in the sighting
def create_large_sighting(flask_app_client, user, request, test_root):
    import tests.extensions.tus.utils as tus_utils
    from tests import utils as test_utils

    transaction_id, filenames = asset_group_utils.create_bulk_tus_transaction(test_root)
    uuids = {'transaction': transaction_id}
    request.addfinalizer(lambda: tus_utils.cleanup_tus_dir(transaction_id))
    import random

    locationId = random.randrange(10000)
    sighting_data = {
        'time': '2000-01-01T01:01:01+00:00',
        'timeSpecificity': 'time',
        'locationId': f'Location {locationId}',
        'encounters': [
            {
                'decimalLatitude': test_utils.random_decimal_latitude(),
                'decimalLongitude': test_utils.random_decimal_longitude(),
                'verbatimLocality': 'Tiddleywink',
                'locationId': f'Location {locationId}',
            },
            {
                'decimalLatitude': test_utils.random_decimal_latitude(),
                'decimalLongitude': test_utils.random_decimal_longitude(),
                'verbatimLocality': 'Tiddleywink',
                'locationId': f'Location {locationId}',
            },
        ],
        'assetReferences': [
            filenames[0],
            filenames[1],
            filenames[2],
            filenames[3],
        ],
    }

    group_data = {
        'description': 'This is a test asset_group, please ignore',
        'uploadType': 'bulk',
        'speciesDetectionModel': [
            'None',
        ],
        'transactionId': transaction_id,
        'sightings': [
            sighting_data,
        ],
    }

    # Use shared helper to create the asset group and extract the uuids
    asset_group_uuids = _create_asset_group_extract_uuids(
        flask_app_client, user, group_data, request
    )
    uuids.update(asset_group_uuids)

    # Shared helper to extract the sighting data
    if 'asset_group_sighting' in uuids.keys():
        sighting_uuids = _commit_sighting_extract_uuids(
            flask_app_client, user, uuids['asset_group_sighting']
        )
        uuids.update(sighting_uuids)

    return uuids


# Local helper for the two create functions above that creates the asset group and extracts the uuids
def _create_asset_group_extract_uuids(
    flask_app_client,
    user,
    group_data,
    request,
    expected_status_code=200,
    expected_error=None,
):
    create_resp = asset_group_utils.create_asset_group(
        flask_app_client, user, group_data, expected_status_code, expected_error
    )
    uuids = {}
    if expected_status_code == 200:
        asset_group_uuid = create_resp.json['guid']
        request.addfinalizer(
            lambda: asset_group_utils.delete_asset_group(
                flask_app_client, user, asset_group_uuid
            )
        )
        assert len(create_resp.json['asset_group_sightings']) == 1
        uuids['asset_group'] = asset_group_uuid
        uuids['asset_group_sighting'] = create_resp.json['asset_group_sightings'][0][
            'guid'
        ]
        uuids['assets'] = [asset['guid'] for asset in create_resp.json['assets']]

    return uuids


def _commit_sighting_extract_uuids(
    flask_app_client, user, asset_group_sighting_guid, expected_status_code=200
):
    uuids = {}

    # Commit the sighting
    commit_resp = asset_group_utils.commit_asset_group_sighting(
        flask_app_client,
        user,
        asset_group_sighting_guid,
        expected_status_code=expected_status_code,
    )
    if expected_status_code != 200:
        return
    sighting_uuid = commit_resp.json['guid']

    # Return all the uuids of things created so that each test can do with them what they choose.
    # Note it is not the responsibility of this code to duplicate the validation of the asset group create
    # and commit responses
    uuids['sighting'] = sighting_uuid
    uuids['encounters'] = [enc['guid'] for enc in commit_resp.json['encounters']]

    return uuids


def cleanup_sighting(flask_app_client, user, uuids):
    if 'transaction' in uuids.keys():
        tus_utils.cleanup_tus_dir(uuids['transaction'])
    if 'asset_group' in uuids.keys():
        asset_group_utils.delete_asset_group(flask_app_client, user, uuids['asset_group'])


def read_sighting(flask_app_client, user, sight_guid, expected_status_code=200):
    response = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        'sightings:read',
        f'{PATH}{sight_guid}',
        expected_status_code,
        response_200=EXPECTED_FIELDS,
    )

    if expected_status_code == 200:
        assert response.json['guid'] == str(sight_guid)
    return response


# As above but does not assume any format output, can be used for sub paths
def read_sighting_path(
    flask_app_client, regular_user, sighting_path, expected_status_code=200
):
    with flask_app_client.login(regular_user, auth_scopes=('sightings:read',)):
        response = flask_app_client.get(f'{PATH}{sighting_path}')
    assert response.status_code == expected_status_code
    return response


# as above but post to the path rather than read from it
def write_sighting_path(
    flask_app_client, regular_user, sighting_path, data, expected_status_code=200
):
    with flask_app_client.login(regular_user, auth_scopes=('sightings:write',)):
        response = flask_app_client.post(
            f'{PATH}{sighting_path}',
            content_type='application/json',
            data=json.dumps(data),
        )
    assert response.status_code == expected_status_code
    return response


def patch_sighting(
    flask_app_client,
    user,
    sighting_guid,
    patch_data=[],
    headers=None,
    expected_status_code=200,
):
    response = test_utils.patch_via_flask(
        flask_app_client,
        user,
        'sightings:write',
        '%s%s' % (PATH, sighting_guid),
        patch_data,
        expected_status_code,
        set(),
        headers=headers,
    )
    if expected_status_code == 200:
        if 'version' in response.json.keys():
            assert response.json.keys() >= EXPECTED_FIELDS
        else:
            assert response.json.keys() >= {'result', 'success'}
            assert response.json['success']
    elif expected_status_code != 401 and expected_status_code != 409:
        assert not response.json['success']

    return response


def delete_sighting(
    flask_app_client, user, sight_guid, expected_status_code=204, headers=None
):
    with flask_app_client.login(user, auth_scopes=('sightings:write',)):
        response = flask_app_client.delete('%s%s' % (PATH, sight_guid), headers=headers)

    if expected_status_code == 204:
        assert response.status_code == 204, response.json
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


# Create a default valid Sage detection response (to allow for the test to corrupt it accordingly)
def build_sage_identification_response(job_uuid, annot_uuid, algorithm):

    # Generate the response back from Sage.
    # 15th July, Do not assume this is correct. This is hacky first try and probably needs
    # expanding depending on algorithm
    sage_resp = {
        'response': {
            'jobid': f'{str(job_uuid)}',
            'json_result': {
                'cm_dict': {annot_uuid: {}},
                'inference_dict': {},
                'query_annot_uuid_list': [annot_uuid],
                'query_config_dict': {
                    'pipeline_root': algorithm,
                },
                'summary_annot': [
                    {
                        'daid': 353909,
                        'dnid': 101124,
                        'duuid': str(uuid.uuid4()),
                        'score': 0.49249419758140284,
                        'species': 'tursiops_truncatus',
                        'viewpoint': 'left',
                    },
                ],
                'summary_name': [
                    {
                        'daid': 354564,
                        'dnid': 78920,
                        'duuid': str(uuid.uuid4()),
                        'score': 4.755731035123042,
                        'species': 'tursiops_truncatus',
                        'viewpoint': 'right',
                    },
                ],
            },
            'status': 'completed',
        },
        'status': {
            'cache': -1,
            'code': 200,
            'message': {},
            'success': True,
        },
    }

    return sage_resp


def send_sage_identification_response(
    flask_app_client,
    user,
    sighting_guid,
    job_guid,
    data,
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('sightings:write',)):
        response = flask_app_client.post(
            f'{PATH}{sighting_guid}/sage_identified/{job_guid}',
            content_type='application/json',
            data=json.dumps(data),
        )
    if expected_status_code == 200:
        assert response.status_code == expected_status_code
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response
