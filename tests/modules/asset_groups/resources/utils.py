# -*- coding: utf-8 -*-
"""
Asset_group resources utils
-------------
"""
import config
import json
import os
import re
import shutil
from unittest import mock
import tests.extensions.tus.utils as tus_utils
import tests.modules.individuals.resources.utils as individual_utils

from tests import utils as test_utils
from tests import TEST_ASSET_GROUP_UUID, TEST_EMPTY_ASSET_GROUP_UUID

PATH = '/api/v1/asset_groups/'
EXPECTED_ASSET_GROUP_SIGHTING_FIELDS = {
    'guid',
    'stage',
    'decimalLatitude',
    'decimalLongitude',
    'encounters',
    'locationId',
    'startTime',
    'completion',
    'assets',
}

ANNOTATION_UUIDS = [
    '1891ca05-5fa5-4e52-bb30-8ee80941c2fc',
    '0c6f3a16-c3f0-4f8d-a47d-951e49b0dacb',
]

DERIVED_MD5SUM_VALUES = {
    'phoenix.jpg': 'da06dc2f5ad273b058217d26f5aa1858',
    'coelacanth.png': 'b6ba153ff160ad4d21ab7b42fbe51892',
    'zebra.jpg': '9c2e4476488534c05b7c557a0e663ccd',
    'fluke.jpg': '0b546f813ec9631ce5c9b1dd579c623b',
}


class AssetGroupCreationData(object):
    def __init__(self, transaction_id, populate_default=True):

        if not populate_default:
            self.content = {}
        else:
            self.content = {
                'description': 'This is a test asset_group, please ignore',
                'uploadType': 'form',
                'speciesDetectionModel': [
                    'None',
                ],
                'transactionId': transaction_id,
                'sightings': [
                    {
                        'startTime': '2000-01-01T01:01:01Z',
                        # Yes, that really is a location, it's a village in Wiltshire https://en.wikipedia.org/wiki/Tiddleywink
                        'locationId': 'Tiddleywink',
                        'encounters': [{}],
                    },
                ],
            }

    def add_filename(self, sighting, filename):
        if 'assetReferences' not in self.content['sightings'][sighting]:
            self.content['sightings'][sighting]['assetReferences'] = []
        self.content['sightings'][sighting]['assetReferences'].append(filename)

    def add_sighting(self, location):
        self.content['sightings'].append(
            {
                'locationId': location,
                'startTime': '2000-01-01T01:01:01Z',
                'assetReferences': [],
                'encounters': [],
            }
        )

    def add_encounter(self, sighting):
        self.content['sightings'][sighting]['encounters'].append({})

    def set_field(self, field, value):
        self.content[field] = value

    def remove_field(self, field):
        del self.content[field]

    def set_sighting_field(self, sighting, field, value):
        self.content['sightings'][sighting][field] = value

    def set_encounter_field(self, sighting, encounter, field, value):
        self.content['sightings'][sighting]['encounters'][encounter][field] = value

    def remove_encounter_field(self, sighting, encounter, field):
        del self.content['sightings'][sighting]['encounters'][encounter][field]

    def get(self):
        return self.content


def create_asset_group(
    flask_app_client, user, data, expected_status_code=200, expected_error=''
):
    from app.modules.asset_groups.tasks import sage_detection

    # Call sage_detection in the foreground by skipping "delay"
    with mock.patch(
        'app.modules.asset_groups.tasks.sage_detection.delay', side_effect=sage_detection
    ):
        if user:
            with flask_app_client.login(user, auth_scopes=('asset_groups:write',)):
                response = flask_app_client.post(
                    '%s' % PATH,
                    content_type='application/json',
                    data=json.dumps(data),
                )
        else:
            response = flask_app_client.post(
                '%s' % PATH,
                content_type='application/json',
                data=json.dumps(data),
            )

    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'guid', 'description', 'major_type'}
        )
    elif 400 <= expected_status_code < 500:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
        assert response.json['message'] == expected_error, response.json['message']
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


# As for method above but simulate a successful initial response from Sage and do some minimal validation
def create_asset_group_sim_sage_init_resp(
    flask_app, flask_app_client, user, data, expected_status_code=200, expected_error=''
):
    # Simulate a valid response from Sage but don't actually send the request to Sage
    with mock.patch.object(
        flask_app.acm,
        'request_passthrough_result',
        return_value={'success': True},
    ) as detection_started:
        from app.modules.asset_groups import tasks

        with mock.patch.object(
            tasks.sage_detection,
            'delay',
            side_effect=lambda *args, **kwargs: tasks.sage_detection(*args, **kwargs),
        ):
            resp = create_asset_group(
                flask_app_client, user, data, expected_status_code, expected_error
            )
        passed_args = detection_started.call_args[0]
        try:
            assert passed_args[:-2] == ('job.detect_request', 'post')
            params = passed_args[-2]['params']
            assert set(params.keys()) >= {
                'endpoint',
                'jobid',
                'input',
                'image_uuid_list',
                'callback_url',
                'callback_detailed',
            }
            assert set(params['input'].keys()) >= {
                'start_detect',
                'labeler_algo',
                'labeler_model_tag',
                'model_tag',
            }
            assert params['endpoint'] == '/api/engine/detect/cnn/lightnet/'
            assert re.match('[a-f0-9-]{36}', params['jobid'])
            assert re.match(
                r'houston\+http://houston:5000/api/v1/asset_groups/sighting/[a-f0-9-]{36}/sage_detected/'
                + params['jobid'],
                params['callback_url'],
            )
            assert all(
                re.match(
                    r'houston\+http://houston:5000/api/v1/assets/src_raw/[a-f0-9-]{36}',
                    uri,
                )
                for uri in json.loads(params['image_uuid_list'])
            )
        except Exception:
            # Calling code cannot clear up the asset group as the resp is not passed if any of the assertions fail
            # meaning that all subsequent tests would fail.
            if 'guid' in resp.json:
                delete_asset_group(flask_app_client, user, resp.json['guid'])
            raise
        return resp


# Helper as many bulk uploads use a common set of files
def create_bulk_tus_transaction(test_root):
    import tests.extensions.tus.utils as tus_utils

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    tus_utils.prep_tus_dir(test_root, filename='coelacanth.png')
    tus_utils.prep_tus_dir(test_root, filename='fluke.jpg')
    tus_utils.prep_tus_dir(test_root, filename='phoenix.jpg')
    return transaction_id, [test_filename, 'coelacanth.png', 'fluke.jpg', 'phoenix.jpg']


def get_bulk_creation_data(test_root, request, species_detection_model=None):
    transaction_id, first_filename = tus_utils.prep_tus_dir(test_root)
    tus_utils.prep_tus_dir(test_root, filename='coelacanth.png')
    tus_utils.prep_tus_dir(test_root, filename='fluke.jpg')
    tus_utils.prep_tus_dir(test_root, filename='phoenix.jpg')
    request.addfinalizer(lambda: tus_utils.cleanup_tus_dir(transaction_id))

    data = AssetGroupCreationData(transaction_id)
    data.add_filename(0, first_filename)
    data.add_encounter(0)
    data.add_filename(0, 'coelacanth.png')
    data.add_sighting('Hogpits Bottom')
    data.add_encounter(1)
    data.add_filename(1, 'fluke.jpg')
    data.add_encounter(1)
    data.add_filename(1, 'phoenix.jpg')
    data.set_field('uploadType', 'bulk')
    if species_detection_model:
        data.set_field('speciesDetectionModel', [species_detection_model])

    return data


def get_bulk_creation_data_one_sighting(transaction_id, test_filename):
    data = AssetGroupCreationData(transaction_id)
    data.add_filename(0, test_filename)
    data.add_encounter(0)
    data.add_filename(0, 'fluke.jpg')
    data.add_encounter(0)
    data.add_filename(0, 'coelacanth.png')
    data.add_encounter(0)
    data.add_filename(0, 'phoenix.jpg')
    data.set_field('uploadType', 'bulk')
    return data


# Create a default valid Sage detection response (to allow for the test to corrupt it accordingly)
def build_sage_detection_response(asset_group_sighting_guid, job_uuid):
    from app.modules.asset_groups.models import AssetGroupSighting
    import uuid

    asset_group_sighting = AssetGroupSighting.query.get(asset_group_sighting_guid)
    asset_ids = list(asset_group_sighting.jobs.values())[-1]['asset_ids']

    # Generate the response back from Sage
    sage_resp = {
        'status': 'completed',
        'jobid': str(job_uuid),
        'json_result': {
            'image_uuid_list': [
                # Image UUID stored in acm (not the same as houston)
                {'__UUID__': str(uuid.uuid4())}
                for _ in asset_ids
            ],
            'results_list': [
                [
                    {
                        'id': 1,
                        'uuid': {'__UUID__': ANNOTATION_UUIDS[0]},
                        'xtl': 459,
                        'ytl': 126,
                        'left': 459,
                        'top': 126,
                        'width': 531,
                        'height': 539,
                        'theta': 0.0,
                        'confidence': 0.8568,
                        'class': 'zebra_plains',
                        'species': 'zebra_plains',
                        'viewpoint': 'test',
                        'quality': None,
                        'multiple': False,
                        'interest': False,
                    },
                    {
                        'id': 2,
                        'uuid': {'__UUID__': ANNOTATION_UUIDS[1]},
                        'xtl': 26,
                        'ytl': 145,
                        'left': 26,
                        'top': 145,
                        'width': 471,
                        'height': 500,
                        'theta': 0.0,
                        'confidence': 0.853,
                        'class': 'zebra_plains',
                        'species': 'zebra_plains',
                        'viewpoint': 'test',
                        'quality': None,
                        'multiple': False,
                        'interest': False,
                    },
                ],
            ],
        },
    }

    # Make sure results_list is the same length as the assets (just
    # empty [])
    sage_resp['json_result']['results_list'] += [[] for _ in range(len(asset_ids) - 1)]
    return sage_resp


def validate_file_data(data, filename):
    import hashlib

    assert hashlib.md5(data).hexdigest() == DERIVED_MD5SUM_VALUES[filename]


def send_sage_detection_response(
    flask_app_client,
    user,
    asset_group_sighting_guid,
    job_guid,
    data,
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('asset_group_sightings:write',)):
        response = flask_app_client.post(
            f'{PATH}sighting/{asset_group_sighting_guid}/sage_detected/{job_guid}',
            content_type='application/json',
            data=json.dumps(data),
        )
    if expected_status_code == 200:
        assert response.status_code == expected_status_code, response.status_code
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


# Does all up to the curation stage using simulated Sage Interactions
def create_asset_group_to_curation(
    flask_app, flask_app_client, user, internal_user, test_root, request
):
    # pylint: disable=invalid-name
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )

    asset_group_uuid = None
    data = get_bulk_creation_data(test_root, request)
    # Use a real detection model to trigger a request sent to Sage
    data.set_field('speciesDetectionModel', ['african_terrestrial'])

    # and the sim_sage util to catch it
    resp = create_asset_group_sim_sage_init_resp(
        flask_app, flask_app_client, user, data.get()
    )
    asset_group_uuid = resp.json['guid']
    request.addfinalizer(
        lambda: delete_asset_group(flask_app_client, user, asset_group_uuid)
    )
    asset_group_sighting1_guid = resp.json['asset_group_sightings'][0]['guid']

    ags1 = AssetGroupSighting.query.get(asset_group_sighting1_guid)
    assert ags1

    job_uuids = [guid for guid in ags1.jobs.keys()]
    assert len(job_uuids) == 1
    job_uuid = job_uuids[0]
    assert ags1.jobs[job_uuid]['model'] == 'african_terrestrial'

    # Simulate response from Sage
    sage_resp = build_sage_detection_response(asset_group_sighting1_guid, job_uuid)
    send_sage_detection_response(
        flask_app_client,
        internal_user,
        asset_group_sighting1_guid,
        job_uuid,
        sage_resp,
    )
    assert ags1.stage == AssetGroupSightingStage.curation

    return asset_group_uuid, asset_group_sighting1_guid


def commit_asset_group_sighting(
    flask_app_client,
    user,
    asset_group_sighting_guid,
    expected_status_code=200,
):
    return test_utils.post_via_flask(
        flask_app_client,
        user,
        scopes='asset_group_sightings:write',
        path=f'{PATH}sighting/{asset_group_sighting_guid}/commit',
        data={},
        expected_status_code=expected_status_code,
        response_200={'guid'},
    )


def commit_asset_group_sighting_sage_identification(
    flask_app,
    flask_app_client,
    user,
    asset_group_sighting_guid,
    expected_status_code=200,
):
    from app.modules.sightings import tasks

    # Start ID simulating success response from Sage
    with mock.patch.object(
        flask_app.acm,
        'request_passthrough_result',
        return_value={'success': True},
    ):
        with mock.patch.object(
            tasks.send_identification,
            'delay',
            side_effect=lambda *args, **kwargs: tasks.send_identification(
                *args, **kwargs
            ),
        ):
            response = commit_asset_group_sighting(
                flask_app_client, user, asset_group_sighting_guid, expected_status_code
            )
    return response


def create_asset_group_with_annotation(
    flask_app_client, db, user, transaction_id, test_filename
):
    data = AssetGroupCreationData(transaction_id)
    data.add_filename(0, test_filename)
    response = create_asset_group(flask_app_client, user, data.get())
    asset_group_uuid = response.json['guid']
    asset_group_sighting_guid = response.json['asset_group_sightings'][0]['guid']
    asset_uuid = response.json['assets'][0]['guid']
    annot_uuid = patch_in_dummy_annotation(
        flask_app_client, db, user, asset_group_sighting_guid, asset_uuid
    )
    return asset_group_uuid, asset_group_sighting_guid, annot_uuid


# Many tests require a committed assetgroup with one sighting, use this helper
def create_and_commit_asset_group(
    flask_app_client, db, user, transaction_id, test_filename
):
    (
        asset_group_uuid,
        asset_group_sighting_uuid,
        annot_uuid,
    ) = create_asset_group_with_annotation(
        flask_app_client, db, user, transaction_id, test_filename
    )

    response = commit_asset_group_sighting(
        flask_app_client, user, asset_group_sighting_uuid
    )

    sighting_uuid = response.json['guid']
    return asset_group_uuid, sighting_uuid, annot_uuid


def create_asset_group_and_sighting(
    flask_app_client, user, request, test_root=None, data=None
):
    from app.modules.sightings.models import Sighting
    from app.modules.asset_groups.models import AssetGroup

    if not data:
        # Need at least one of them set
        assert test_root is not None
        transaction_id, filenames = create_bulk_tus_transaction(test_root)
        request.addfinalizer(lambda: tus_utils.cleanup_tus_dir(transaction_id))
        import random

        locationId = random.randrange(10000)
        data = {
            'description': 'This is a test asset_group, please ignore',
            'uploadType': 'bulk',
            'speciesDetectionModel': ['None'],
            'transactionId': transaction_id,
            'sightings': [
                {
                    'startTime': '2000-01-01T01:01:01Z',
                    'locationId': f'Location {locationId}',
                    'encounters': [
                        {
                            'decimalLatitude': test_utils.random_decimal_latitude(),
                            'decimalLongitude': test_utils.random_decimal_longitude(),
                            # Yes, that really is a location, it's a village in Wiltshire
                            # https://en.wikipedia.org/wiki/Tiddleywink
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
                },
            ],
        }

    create_response = create_asset_group(flask_app_client, user, data)
    asset_group_uuid = create_response.json['guid']
    request.addfinalizer(
        lambda: delete_asset_group(flask_app_client, user, asset_group_uuid)
    )
    asset_group = AssetGroup.query.get(asset_group_uuid)
    assert create_response.json['description'] == data['description']
    assert create_response.json['owner_guid'] == str(user.guid)

    # Commit them all
    sightings = []
    for asset_group_sighting in create_response.json['asset_group_sightings']:
        commit_response = commit_asset_group_sighting(
            flask_app_client, user, asset_group_sighting['guid']
        )
        sighting_uuid = commit_response.json['guid']
        sighting = Sighting.query.get(sighting_uuid)
        sightings.append(sighting)
        request.addfinalizer(lambda: sighting.delete_cascade())

    return asset_group, sightings


def create_asset_group_with_sighting_and_individual(
    flask_app_client,
    user,
    request,
    test_root=None,
    asset_group_data=None,
    individual_data=None,
):
    from app.modules.individuals.models import Individual

    asset_group, sightings = create_asset_group_and_sighting(
        flask_app_client, user, request, test_root, asset_group_data
    )

    # Extract the encounters to use to create an individual
    encounters = sightings[0].encounters
    assert len(encounters) >= 1
    if individual_data:
        individual_data['encounters'] = [{'id': str(encounters[0].guid)}]
    else:
        individual_data = {'encounters': [{'id': str(encounters[0].guid)}]}

    individual_response = individual_utils.create_individual(
        flask_app_client, user, 200, individual_data
    )

    individual_guid = individual_response.json['result']['id']
    request.addfinalizer(
        lambda: individual_utils.delete_individual(
            flask_app_client, user, individual_guid
        )
    )
    individual = Individual.query.get(individual_guid)
    return asset_group, sightings, individual


def patch_asset_group(
    flask_app_client, user, asset_group_guid, data, expected_status_code=200
):
    return test_utils.patch_via_flask(
        flask_app_client,
        user,
        scopes='asset_groups:write',
        path=f'{PATH}{asset_group_guid}',
        data=data,
        expected_status_code=expected_status_code,
        response_200={'guid', 'description', 'major_type'},
    )


def read_asset_group(flask_app_client, user, asset_group_guid, expected_status_code=200):

    return test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='asset_groups:read',
        path=f'{PATH}{asset_group_guid}',
        expected_status_code=expected_status_code,
        response_200={'guid', 'description', 'major_type'},
    )


def read_all_asset_groups(flask_app_client, user, expected_status_code=200):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='asset_groups:read',
        path=PATH,
        expected_status_code=expected_status_code,
    )


def delete_asset_group(
    flask_app_client, user, asset_group_guid, expected_status_code=204
):
    from app.modules.asset_groups.models import AssetGroup
    from app.modules.asset_groups.tasks import delete_remote

    with mock.patch('app.modules.asset_groups.tasks') as tasks:
        # Do delete_remote in the foreground immediately instead of using a
        # celery worker in the background
        tasks.delete_remote.delay.side_effect = lambda *args, **kwargs: delete_remote(
            *args, **kwargs
        )
        with flask_app_client.login(user, auth_scopes=('asset_groups:write',)):
            response = flask_app_client.delete('%s%s' % (PATH, asset_group_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
        assert not AssetGroup.is_on_remote(asset_group_guid)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )


def patch_asset_group_sighting(
    flask_app_client,
    user,
    patch_path,
    data,
    expected_status_code=200,
    expected_resp='',
):
    with flask_app_client.login(user, auth_scopes=('asset_group_sightings:write',)):
        response = flask_app_client.patch(
            f'{PATH}sighting/{patch_path}',
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'stage', 'config'})
    elif expected_status_code == 400:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message', 'passed_message'}
        )
        assert response.json['passed_message'] == expected_resp
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def patch_asset_group_sighting_as_sighting(
    flask_app_client,
    user,
    patch_path,
    data,
    expected_status_code=200,
):
    with flask_app_client.login(user, auth_scopes=('asset_group_sightings:write',)):
        response = flask_app_client.patch(
            f'{PATH}sighting/as_sighting/{patch_path}',
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        # startTime and locationId are only present in the _as_sighting endpoints,
        # since they are in the config of a standard AGS
        test_utils.validate_dict_response(
            response,
            200,
            {'guid', 'stage', 'completion', 'assets', 'startTime', 'locationId'},
        )
    elif expected_status_code == 400:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message', 'passed_message'}
        )
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_asset_group_sighting(
    flask_app_client, user, asset_group_sighting_guid, expected_status_code=200
):
    response = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='asset_group_sightings:read',
        path=f'{PATH}sighting/{asset_group_sighting_guid}',
        expected_status_code=expected_status_code,
        response_200={
            'guid',
            'stage',
            'config',
            'completion',
            'assets',
            'creator',
            'asset_group_guid',
            'sighting_guid',
        },
    )
    # so we can capture the example if we want, via -s flag on pytest
    print('Asset Group Sighting: ')
    print(json.dumps(response.json, indent=4, sort_keys=True))
    return response


def read_asset_group_sighting_as_sighting(
    flask_app_client, user, asset_group_sighting_guid, expected_status_code=200
):
    response = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='asset_group_sightings:read',
        path=f'{PATH}sighting/as_sighting/{asset_group_sighting_guid}',
        expected_status_code=expected_status_code,
        # startTime and locationId are only present in the _as_sighting endpoints,
        # since they are in the config of a standard AGS
        response_200={
            'guid',
            'stage',
            'completion',
            'assets',
            'startTime',
            'locationId',
            'creator',
            'asset_group_guid',
            'sightingGuid',
        },
    )
    # so we can capture the example if we want, via -s flag on pytest
    print('Asset Group Sighting As Sighting: ')
    print(json.dumps(response.json, indent=4, sort_keys=True))
    return response


def simulate_job_detection_response(
    flask_app_client,
    user,
    asset_group_sighting_uuid,
    asset_guid,
    job_id,
    expected_status_code=200,
):
    path = f'sighting/{asset_group_sighting_uuid}/sage_detected/{job_id}'
    data = build_sage_detection_response(asset_group_sighting_uuid, job_id)

    return simulate_detection_response(
        flask_app_client,
        user,
        path,
        data,
        expected_status_code,
    )


def simulate_detection_response(
    flask_app_client, user, path, data, expected_status_code=200
):
    with flask_app_client.login(user, auth_scopes=('asset_group_sightings:write',)):
        response = flask_app_client.post(
            f'{PATH}{path}',
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        assert expected_status_code == response.status_code
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


# Helper as used across multiple tests
def patch_in_dummy_annotation(
    flask_app_client, db, user, asset_group_sighting_uuid, asset_uuid, encounter_num=0
):
    from app.modules.assets.models import Asset
    from app.modules.annotations.models import Annotation
    import uuid

    asset = Asset.find(asset_uuid)
    assert asset

    # Create a dummy annotation for this Sighting
    new_annot = Annotation(
        guid=uuid.uuid4(),
        content_guid=uuid.uuid4(),
        asset=asset,
        ia_class='none',
        viewpoint='test',
        bounds={'rect': [45, 5, 78, 3], 'theta': 4.8},
    )
    with db.session.begin(subtransactions=True):
        db.session.add(new_annot)

    # Patch it in
    group_sighting = read_asset_group_sighting(
        flask_app_client, user, asset_group_sighting_uuid
    )
    encounter_guid = group_sighting.json['config']['encounters'][encounter_num]['guid']

    patch_data = [
        test_utils.patch_replace_op('annotations', [str(new_annot.content_guid)])
    ]
    patch_asset_group_sighting(
        flask_app_client,
        user,
        f'{asset_group_sighting_uuid}/encounter/{encounter_guid}',
        patch_data,
    )
    return new_annot.guid


def detect_asset_group_sighting(
    flask_app_client, user, asset_group_sighting_uuid, expected_status_code=200
):

    with flask_app_client.login(user, auth_scopes=('asset_group_sightings:write',)):
        response = flask_app_client.post(
            f'{PATH}sighting/{asset_group_sighting_uuid}/detect',
            content_type='application/json',
        )
    if expected_status_code == 200:
        test_utils.validate_dict_response(response, 200, {'guid', 'stage', 'config'})
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


# multiple tests clone a asset_group, do something with it and clean it up. Make sure this always happens using a
# class with a cleanup method to be called if any assertions fail
class CloneAssetGroup(object):
    def __init__(self, client, owner, guid, force_clone):
        from app.modules.asset_groups.models import AssetGroup

        self.asset_group = None
        self.guid = guid

        # Allow the option of forced cloning, this could raise an exception if the assertion fails
        # but this does not need to be in any try/except/finally construct as no resources are allocated yet
        if force_clone:
            database_path = config.TestingConfig.ASSET_GROUP_DATABASE_PATH
            asset_group_path = os.path.join(database_path, str(guid))

            if os.path.exists(asset_group_path):
                shutil.rmtree(asset_group_path)
            assert not os.path.exists(asset_group_path)

        url = f'{PATH}{guid}'
        with client.login(owner, auth_scopes=('asset_groups:read',)):
            self.response = client.get(url)

        # only store the asset_group if the clone worked
        if self.response.status_code == 200:
            self.asset_group = AssetGroup.query.get(self.response.json['guid'])

        elif self.response.status_code in (428, 403):
            # 428 Precondition Required
            # 403 Forbidden
            with client.login(owner, auth_scopes=('asset_groups:write',)):
                self.response = client.post(url)

            # only store the asset_group if the clone worked
            if self.response.status_code == 200:
                self.asset_group = AssetGroup.query.get(self.response.json['guid'])

        else:
            assert (
                False
            ), f'url={url} status_code={self.response.status_code} data={self.response.data}'

    def remove_files(self):
        database_path = config.TestingConfig.ASSET_GROUP_DATABASE_PATH
        asset_group_path = os.path.join(database_path, str(self.guid))
        if os.path.exists(asset_group_path):
            shutil.rmtree(asset_group_path)

    def cleanup(self):
        # Restore original state if not one of the asset group fixtures
        if str(self.guid) not in (TEST_ASSET_GROUP_UUID, TEST_EMPTY_ASSET_GROUP_UUID):
            if self.asset_group is not None:
                self.asset_group.delete()
                self.asset_group = None
            self.remove_files()


# Clone the asset_group
def clone_asset_group(
    client,
    owner,
    guid,
    force_clone=False,
    expect_failure=False,
):
    clone = CloneAssetGroup(client, owner, guid, force_clone)

    if not expect_failure:
        assert clone.response.status_code == 200, clone.response.data
    return clone
