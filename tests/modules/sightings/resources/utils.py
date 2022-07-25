# -*- coding: utf-8 -*-
"""
Project resources utils
-------------
"""
import json

import tests.extensions.tus.utils as tus_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils
from tests import utils as test_utils

PATH = '/api/v1/sightings/'

EXPECTED_FIELDS = {
    'curation_start_time',
    'created',
    'hasEdit',
    'review_time',
    'created',
    'detection_start_time',
    'locationId',
    'comments',
    'hasView',
    'stage',
    'customFields',
    'creator',
    'updated',
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
    return test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes='',
        path=PATH,
        data=data_in,
        expected_status_code=expected_status_code,
        response_200={'success'},
        expected_error=expected_error,
    )


def create_sighting(
    flask_app_client,
    asset_group_user,
    request,
    test_root,
    sighting_data=None,
    expected_status_code=200,
    expected_error=None,
    commit_expected_status_code=200,
    commit_user=None,
    add_annot=False,
):
    import tests.modules.site_settings.resources.utils as site_setting_utils

    if not commit_user:
        commit_user = asset_group_user

    regions = site_setting_utils.get_and_ensure_test_regions(
        flask_app_client, commit_user
    )
    region1_id = regions[0]['id']

    if not sighting_data:
        # Create a valid but simple one
        sighting_data = {
            'encounters': [{}],
            'time': '2000-01-01T01:01:01+00:00',
            'timeSpecificity': 'time',
            'locationId': region1_id,
        }
    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    uuids = {'transaction': transaction_id}
    group_data = {
        'description': 'This is a test asset_group, please ignore',
        'uploadType': 'form',
        'speciesDetectionModel': ['None'],
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
    asset_group_uuids = asset_group_utils.create_asset_group_extract_uuids(
        flask_app_client,
        asset_group_user,
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
            commit_user,
            uuids['asset_group_sighting'],
            expected_status_code=commit_expected_status_code,
        )
        if sighting_uuids:  # empty if non-200 above
            uuids.update(sighting_uuids)

    return uuids


# Helper that does what the above method does but for multiple files and multiple encounters in the sighting
def create_large_sighting(
    flask_app_client, owner_user, request, test_root, commit_user=None
):
    uuids = asset_group_utils.create_large_asset_group_uuids(
        flask_app_client, owner_user, request, test_root
    )
    if not commit_user:
        commit_user = owner_user

    # Shared helper to extract the sighting data
    if 'asset_group_sighting' in uuids.keys():
        sighting_uuids = _commit_sighting_extract_uuids(
            flask_app_client, commit_user, uuids['asset_group_sighting']
        )
        uuids.update(sighting_uuids)

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
        '{}{}'.format(PATH, sighting_guid),
        patch_data,
        expected_status_code,
        set(),
        headers=headers,
    )
    if expected_status_code == 200:
        if response.json.keys() <= EXPECTED_FIELDS:
            header_dict = dict(headers)
            if header_dict.get('x-allow-delete-cascade-sighting', False):
                # sighting almost certainly being deleted so no response perfectly plausible
                return response

        assert (
            response.json.keys() >= EXPECTED_FIELDS
        ), f'expected {EXPECTED_FIELDS}, got {response.json}'

    return response


def delete_sighting(
    flask_app_client, user, sight_guid, expected_status_code=204, headers=None
):
    with flask_app_client.login(user, auth_scopes=('sightings:write',)):
        response = flask_app_client.delete(
            '{}{}'.format(PATH, sight_guid), headers=headers
        )

    if expected_status_code == 204:
        assert response.status_code == 204, response.json
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response
