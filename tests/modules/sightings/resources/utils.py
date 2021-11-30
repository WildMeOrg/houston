# -*- coding: utf-8 -*-
"""
Project resources utils
-------------
"""
import json
import uuid

from tests import utils as test_utils
from flask import current_app
import os
import shutil
from app.extensions.tus import tus_upload_dir


PATH = '/api/v1/sightings/'


def get_transaction_id():
    return '11111111-1111-1111-1111-111111111111'


def prep_tus_dir(test_root, transaction_id=None, filename='zebra.jpg'):
    if transaction_id is None:
        transaction_id = get_transaction_id()

    image_file = os.path.join(test_root, filename)

    upload_dir = tus_upload_dir(current_app, transaction_id=transaction_id)
    if not os.path.isdir(upload_dir):
        os.mkdir(upload_dir)
    shutil.copy(image_file, upload_dir)
    size = os.path.getsize(image_file)
    assert size > 0
    return transaction_id, filename


# should always follow the above when finished
def cleanup_tus_dir(tid):
    upload_dir = tus_upload_dir(current_app, transaction_id=tid)
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)


# note: default data_in will fail
def create_sighting(
    flask_app_client,
    user,
    test_root,
    request,
    data_in={'locationId': 'PYTEST', 'startTime': '2000-01-01T01:01:01Z'},
    expected_status_code=200,
    expected_error=None,
):
    from tests.modules.asset_groups.resources import utils as asset_group_utils

    asset_group_data = asset_group_utils.AssetGroupCreationData()

    asset_group, sightings = asset_group_utils.create_asset_group_and_sighting(
        flask_app_client,
        user,
        test_root,
        request,
        asset_group_data.get(),
    )
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
        assert not response.json['success']
        assert response.json['message'] == 'Error'
        if expected_error:
            assert response.json['passed_message'] == expected_error

    return response


def read_sighting(flask_app_client, user, sight_guid, expected_status_code=200):
    response = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        'sightings:read',
        f'{PATH}{sight_guid}',
        expected_status_code,
        response_200={'id', 'creator', 'encounters', 'stage', 'assets'},
    )

    if expected_status_code == 200:
        assert response.json['id'] == str(sight_guid)
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
            assert response.json.keys() >= {'version', 'guid', 'id'}
        else:
            assert response.json.keys() >= {'result', 'success'}
            assert response.json['success']
    elif expected_status_code != 401:
        assert not response.json['success']

    return response


def delete_sighting(flask_app_client, user, sight_guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('sightings:write',)):
        response = flask_app_client.delete('%s%s' % (PATH, sight_guid))

    if expected_status_code == 204:
        assert response.status_code == 204, response.json
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )


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
