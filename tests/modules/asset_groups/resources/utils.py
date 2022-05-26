# -*- coding: utf-8 -*-
"""
Asset_group resources utils
-------------
"""
import json
import os
import shutil
from unittest import mock

from config import get_preliminary_config

import tests.extensions.tus.utils as tus_utils
from tests import utils as test_utils


PATH = '/api/v1/asset_groups/'
EXPECTED_ASSET_GROUP_SIGHTING_FIELDS = {
    'guid',
    'stage',
    'decimalLatitude',
    'decimalLongitude',
    'encounters',
    'locationId',
    'time',
    'timeSpecificity',
    'assets',
}

ANNOTATION_UUIDS = [
    '1891ca05-5fa5-4e52-bb30-8ee80941c2fc',
    '0c6f3a16-c3f0-4f8d-a47d-951e49b0dacb',
]

###################################################################################################################
# Simple helpers for use with most tests
###################################################################################################################


# Helper for 'normal' tests that don't want to do something clever with the asset group
def create_simple_asset_group(flask_app_client, user, request, test_root):

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    request.addfinalizer(lambda: tus_utils.cleanup_tus_dir(transaction_id))

    data = AssetGroupCreationData(transaction_id, test_filename)
    response = create_asset_group(flask_app_client, user, data.get())

    json_resp = response.json
    group_guid = json_resp['guid']
    asset_guids = [asset['guid'] for asset in json_resp['assets']]
    ags_guids = [ags['guid'] for ags in json_resp['asset_group_sightings']]

    assert len(ags_guids) == 1
    assert len(asset_guids) == 1
    request.addfinalizer(lambda: delete_asset_group(flask_app_client, user, group_guid))
    return group_guid, ags_guids[0], asset_guids[0]


# as for above but returns uuids as a dict
def create_simple_asset_group_uuids(flask_app_client, user, request, test_root):
    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    request.addfinalizer(lambda: tus_utils.cleanup_tus_dir(transaction_id))

    data = AssetGroupCreationData(transaction_id, test_filename)
    # Use shared helper to create the asset group and extract the uuids
    uuids = create_asset_group_extract_uuids(flask_app_client, user, data.get(), request)

    # Add these two, OK yes they're not uuids but they're useful
    uuids['transaction'] = transaction_id
    uuids['filename'] = test_filename
    return uuids


# Helper that does what the above method does but for multiple files and multiple encounters in the sighting
def create_large_asset_group_uuids(flask_app_client, user, request, test_root):
    import tests.extensions.tus.utils as tus_utils
    from tests import utils as test_utils

    transaction_id, filenames = create_bulk_tus_transaction(test_root)
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
    asset_group_uuids = create_asset_group_extract_uuids(
        flask_app_client, user, group_data, request
    )
    uuids.update(asset_group_uuids)

    return uuids


# Helper as used across multiple tests
def patch_in_dummy_annotation(
    flask_app_client,
    db,
    user,
    asset_group_sighting_uuid,
    asset_uuid,
    encounter_num=0,
    padding=0,
):
    from app.modules.assets.models import Asset
    from app.modules.annotations.models import Annotation
    import uuid

    asset = Asset.find(asset_uuid)
    assert asset

    # Create a dummy annotation for this Sighting
    rect = [
        10 - padding,
        10 - padding,
        390 + padding,
        390 + padding,
    ]
    new_annot = Annotation(
        guid=uuid.uuid4(),
        content_guid=uuid.uuid4(),
        asset=asset,
        ia_class='none',
        viewpoint='test',
        bounds={'rect': rect, 'theta': 4.8},
    )
    with db.session.begin(subtransactions=True):
        db.session.add(new_annot)

    # Patch it in
    group_sighting = read_asset_group_sighting(
        flask_app_client, user, asset_group_sighting_uuid
    )
    encounter_guid = group_sighting.json['config']['sighting']['encounters'][
        encounter_num
    ]['guid']

    patch_data = [test_utils.patch_add_op('annotations', [str(new_annot.guid)])]
    patch_asset_group_sighting(
        flask_app_client,
        user,
        f'{asset_group_sighting_uuid}/encounter/{encounter_guid}',
        patch_data,
    )
    return new_annot.guid


def patch_in_annotations(
    flask_app_client, user, asset_group_sighting_uuid, encounter_guid, annotation_guids
):
    patch_data = [test_utils.patch_add_op('annotations', annotation_guids)]
    patch_asset_group_sighting(
        flask_app_client,
        user,
        f'{asset_group_sighting_uuid}/encounter/{encounter_guid}',
        patch_data,
    )


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
    from app.extensions.git_store.tasks import delete_remote

    with mock.patch('app.extensions.git_store.tasks') as tasks:
        # Do delete_remote in the foreground immediately instead of using a
        # celery worker in the background
        tasks.delete_remote.delay.side_effect = lambda *args, **kwargs: delete_remote(
            *args, **kwargs
        )
        with flask_app_client.login(user, auth_scopes=('asset_groups:write',)):
            response = flask_app_client.delete('%s%s' % (PATH, asset_group_guid))

    if expected_status_code == 204:
        assert response.status_code == 204, response.status_code
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
            response, expected_status_code, {'status', 'message'}
        )
        assert response.json['message'] == expected_resp, response.json['message']
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
    response_200={
        'guid',
        'stage',
        'assets',
        'time',
        'timeSpecificity',
        'locationId',
    },
):
    with flask_app_client.login(user, auth_scopes=('asset_group_sightings:write',)):
        response = flask_app_client.patch(
            f'{PATH}sighting/as_sighting/{patch_path}',
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        # time and locationId are only present in the _as_sighting endpoints,
        # since they are in the config of a standard AGS
        test_utils.validate_dict_response(response, 200, response_200)
    elif expected_status_code == 400:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_asset_group_sightings(flask_app_client, user, expected_status_code=200):
    return test_utils.get_list_via_flask(
        flask_app_client,
        user,
        scopes='asset_groups:read',
        path=f'{PATH}sighting',
        expected_status_code=expected_status_code,
    )


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
            'assets',
            'creator',
            'asset_group_guid',
            'sighting_guid',
        },
    )

    return response


def read_asset_group_sighting_debug(
    flask_app_client, user, asset_group_sighting_guid, expected_status_code=200
):
    response = test_utils.get_dict_via_flask(
        flask_app_client,
        user,
        scopes='asset_group_sightings:read',
        path=f'{PATH}sighting/debug/{asset_group_sighting_guid}',
        expected_status_code=expected_status_code,
        response_200={
            'guid',
            'stage',
            'config',
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
        # time and locationId are only present in the _as_sighting endpoints,
        # since they are in the config of a standard AGS
        response_200={
            'guid',
            'stage',
            'assets',
            'time',
            'timeSpecificity',
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


# Extract datta from AGS response in a format useful for testing
def extract_ags_data(group_data, ags_num):
    ags_data = {
        'guid': group_data['asset_group_sightings'][ags_num]['guid'],
        'encounters': group_data['asset_group_sightings'][ags_num]['config']['sighting'][
            'encounters'
        ],
        'assets': [],
    }
    for filename in group_data['asset_group_sightings'][ags_num]['config']['sighting'][
        'assetReferences'
    ]:
        asset_guids = [
            asset['guid']
            for asset in group_data['assets']
            if asset['filename'] == filename
        ]
        assert len(asset_guids) == 1
        ags_data['assets'].append({'guid': asset_guids[0], 'filename': filename})

    return ags_data


# Helper for create functions that creates the asset group and extracts the uuids
def create_asset_group_extract_uuids(
    flask_app_client,
    user,
    group_data,
    request,
    expected_status_code=200,
    expected_error=None,
):
    create_resp = create_asset_group(
        flask_app_client, user, group_data, expected_status_code, expected_error
    )
    uuids = {}
    if expected_status_code == 200:
        asset_group_uuid = create_resp.json['guid']
        if user:
            # calling code responsibility to clear up if public data
            request.addfinalizer(
                lambda: delete_asset_group(flask_app_client, user, asset_group_uuid)
            )

        assert len(create_resp.json['asset_group_sightings']) == 1
        uuids['asset_group'] = asset_group_uuid
        uuids['asset_group_sighting'] = create_resp.json['asset_group_sightings'][0][
            'guid'
        ]
        uuids['assets'] = [asset['guid'] for asset in create_resp.json['assets']]

    return uuids


###################################################################################################################
# Complexity that is only required for the specific testing of edge cases in the Asset group code
###################################################################################################################


class AssetGroupCreationData(object):
    def __init__(self, transaction_id, filename=None, populate_default=True):

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
                        'time': '2000-01-01T01:01:01+00:00',
                        'timeSpecificity': 'time',
                        # Yes, that really is a location, it's a village in Wiltshire https://en.wikipedia.org/wiki/Tiddleywink
                        'locationId': 'Tiddleywink',
                        'encounters': [{}],
                    },
                ],
            }
            if filename:
                self.add_filename(0, filename)

    def add_filename(self, sighting, filename):
        if 'assetReferences' not in self.content['sightings'][sighting]:
            self.content['sightings'][sighting]['assetReferences'] = []
        self.content['sightings'][sighting]['assetReferences'].append(filename)

    def add_sighting(self, location):
        self.content['sightings'].append(
            {
                'locationId': location,
                'time': '2000-01-01T01:01:01+00:00',
                'timeSpecificity': 'time',
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
    data['token'] = 'XXX'  # Recaptcha bypass

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
        assert response.json['description'] == data['description']
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


def create_asset_group_sim_sage_init_resp(
    flask_app, flask_app_client, user, data, expected_status_code=200, expected_error=''
):
    # Create the AssetGroup and run detection in foreground
    resp = create_asset_group(
        flask_app_client, user, data, expected_status_code, expected_error
    )

    try:
        progress_guids = []
        for ags in resp.json['asset_group_sightings']:
            progress_guids.append(ags['progress_detection']['guid'])
        test_utils.wait_for_progress(flask_app, progress_guids)

    except Exception:
        # Calling code cannot clear up the asset group as the resp is not passed if any of the assertions fail
        # meaning that all subsequent tests would fail.
        if 'guid' in resp.json:
            delete_asset_group(flask_app_client, user, resp.json['guid'])
        raise
    return resp


# Helper as many bulk uploads use a common set of files
def create_bulk_tus_transaction(test_root):

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

    data = AssetGroupCreationData(transaction_id, first_filename)
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


def validate_file_data(test_root, data, filename):
    import hashlib

    from PIL import Image
    import io
    from app.modules.assets.models import Asset

    full_path = f'{test_root}/{filename}'
    full_path = full_path.replace('/code/', '')

    with Image.open(full_path) as source_image:
        source_image.thumbnail(Asset.FORMATS['master'])
        rgb = source_image.convert('RGB')
        # hashlib.md5(source_image.tobytes()).hexdigest()
        # should have worked but didn't
        with io.BytesIO() as mem_file:
            rgb.save(mem_file, 'JPEG')
            md5sum = hashlib.md5(mem_file.getvalue()).hexdigest()

    assert hashlib.md5(data).hexdigest() == md5sum


# As for the normal commit but fake a response from Sage indicating Success
def commit_asset_group_sighting_sage_identification(
    flask_app,
    flask_app_client,
    user,
    asset_group_sighting_guid,
    expected_status_code=200,
):
    from app.modules.annotations.models import Annotation
    from app.extensions import elasticsearch as es

    # Start ID simulating success response from Sage
    with es.session.begin(blocking=True, forced=True):
        Annotation.index_all()
    response = commit_asset_group_sighting(
        flask_app_client, user, asset_group_sighting_guid, expected_status_code
    )
    return response


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
            database_path = get_preliminary_config().ASSET_GROUP_DATABASE_PATH
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
        database_path = get_preliminary_config().ASSET_GROUP_DATABASE_PATH
        asset_group_path = os.path.join(database_path, str(self.guid))
        if os.path.exists(asset_group_path):
            shutil.rmtree(asset_group_path)

    def cleanup(self):
        # Restore original state
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
