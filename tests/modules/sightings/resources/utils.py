# -*- coding: utf-8 -*-
"""
Project resources utils
-------------
"""
import json
import config
from tests import utils as test_utils
from flask import current_app
import os
import shutil
from app.extensions.tus import tus_upload_dir


PATH = '/api/v1/sightings/'


def get_transaction_id():
    return '11111111-1111-1111-1111-111111111111'


def prep_tus_dir():
    transaction_id = get_transaction_id()

    filename = 'zebra.jpg'
    image_file = os.path.join(
        config.TestingConfig.PROJECT_ROOT,
        'tests',
        'submissions',
        'test-000',
        filename,
    )
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
    flask_app_client, user, expected_status_code=200, data_in={'location_id': 'PYTEST'}
):
    if user is not None:
        with flask_app_client.login(user):
            response = flask_app_client.post(
                PATH,
                data=json.dumps(data_in),
                content_type='application/javascript',
            )
    else:
        response = flask_app_client.post(
            PATH,
            data=json.dumps(data_in),
            content_type='application/javascript',
        )

    assert isinstance(response.json, dict)
    assert response.status_code == expected_status_code
    return response


# not yet implemented
def read_sighting(flask_app_client, user, enc_guid, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('sightings:read',)):
        response = flask_app_client.get('%s%s' % (PATH, enc_guid))

    assert isinstance(response.json, dict)
    assert response.status_code == expected_status_code
    if expected_status_code == 200:
        assert response.json['id'] == str(enc_guid)
    return response


# not yet implemented
def delete_sighting(flask_app_client, user, enc_guid, expected_status_code=204):
    with flask_app_client.login(user, auth_scopes=('sighting:write',)):
        response = flask_app_client.delete('%s%s' % (PATH, enc_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
