# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.users.resources.utils as user_utils
import tests.extensions.tus.utils as tus_utils
from unittest import mock


# Test a bunch of failure scenarios
def test_create_asset_group(flask_app_client, researcher_1, readonly_user, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None

    try:
        data = TestCreationData(transaction_id, False)
        data.set_field('description', 'This is a test asset_group, please ignore')

        resp_msg = 'speciesDetectionModel field missing from request'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )
        data.set_field('speciesDetectionModel', [False])

        data.set_field('transactionId', transaction_id)
        resp_msg = 'sightings field missing from request'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_field('sightings', [])
        resp_msg = 'sightings in request must have at least one entry'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_field('sightings', [None])
        resp_msg = 'Sighting 1 needs to be a dict'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_field(
            'sightings',
            [
                {},
            ],
        )
        resp_msg = 'startTime field missing from Sighting 1'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_sighting_field(0, 'startTime', 'never')

        resp_msg = 'encounters field missing from Sighting 1'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_sighting_field(0, 'encounters', [''])
        resp_msg = 'Encounter 1.1 needs to be a dict'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )
        data.set_sighting_field(0, 'encounters', [{}])

        data.set_sighting_field(0, 'assetReferences', '')
        # data.set_encounter_field(0, 0, 'assetReferences', '')
        resp_msg = 'assetReferences incorrect type in Sighting 1'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_sighting_field(0, 'assetReferences', [test_filename])
        resp_msg = "Use uploadType to define type 'bulk' or 'form'"
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_field('uploadType', 'form')

        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )

        asset_group_uuid = resp.json['guid']
        # Read the metadata file and make sure that the frontend sightings are exactly what we sent
        from app.modules.asset_groups.models import AssetGroup
        import os
        import json

        asset_group = AssetGroup.query.get(resp.json['guid'])
        asset_group_path = asset_group.get_absolute_path()
        asset_group_metadata_path = os.path.join(asset_group_path, 'metadata.json')
        assert os.path.exists(asset_group_metadata_path)
        with open(asset_group_metadata_path, 'r') as asset_group_metadata_file:
            metadata_dict = json.load(asset_group_metadata_file)
        file_json = metadata_dict.get('frontend_sightings_data')
        request_json = data.get()
        # Stored data is a superset of what was sent so only check fields sent
        for key in request_json.keys():
            if key != 'sightings':
                assert request_json[key] == file_json[key]
            else:
                for sighting_num in range(len(request_json['sightings'])):
                    for sighting_key in request_json['sightings'][sighting_num].keys():
                        if sighting_key != 'encounters':
                            assert (
                                request_json[key][sighting_num][sighting_key]
                                == file_json[key][sighting_num][sighting_key]
                            )
    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)


def test_create_asset_group_2_assets(flask_app_client, researcher_1, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    tus_utils.prep_tus_dir(test_root, filename='coelacanth.png')
    asset_group_uuid = None
    try:
        data = TestCreationData(transaction_id)
        data.add_filename(0, test_filename)
        data.add_filename(0, 'coelacanth.png')
        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = resp.json['guid']
        assets = sorted(resp.json['assets'], key=lambda a: a['filename'])
        asset_guids = [a['guid'] for a in assets]
        assert assets == [
            {
                'filename': 'coelacanth.png',
                'guid': asset_guids[0],
                'src': f'/api/v1/assets/src/{asset_guids[0]}',
            },
            {
                'filename': 'zebra.jpg',
                'guid': asset_guids[1],
                'src': f'/api/v1/assets/src/{asset_guids[1]}',
            },
        ]
    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)


def test_create_asset_group_no_assets(
    flask_app_client, researcher_1, contributor_1, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData

    asset_group_uuid = None
    sighting_uuid = None
    try:
        data = TestCreationData(None)
        data.remove_field('transactionId')
        # Should fail as not permitted for contributor
        expected_resp = 'Only a Researcher can create an AssetGroup without any Assets'
        asset_group_utils.create_asset_group(
            flask_app_client, contributor_1, data.get(), 400, expected_resp
        )
        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = resp.json['guid']

        # Make sure that the user has a single unprocessed sighting
        user_resp = user_utils.read_user(flask_app_client, researcher_1, 'me')
        assert 'unprocessed_sightings' in user_resp.json
        assert len(user_resp.json['unprocessed_sightings']) == 1
        sighting_uuid = user_resp.json['unprocessed_sightings'][0]
    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        if sighting_uuid:
            import tests.modules.sightings.resources.utils as sighting_utils

            sighting_utils.delete_sighting(flask_app_client, researcher_1, sighting_uuid)


def test_create_asset_group_anonymous(
    flask_app_client, researcher_1, staff_user, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = TestCreationData(transaction_id)
        data.add_filename(0, test_filename)
        data.set_field('submitterEmail', researcher_1.email)
        resp_msg = 'Invalid submitter data'
        asset_group_utils.create_asset_group(
            flask_app_client, None, data.get(), 403, resp_msg
        )
        data.remove_field('submitterEmail')

        data.set_field('bulkUpload', True)
        resp_msg = 'anonymous users not permitted to do bulk upload'
        asset_group_utils.create_asset_group(
            flask_app_client, None, data.get(), 400, resp_msg
        )
        data.set_field('bulkUpload', False)

        data.set_encounter_field(0, 0, 'ownerEmail', researcher_1.email)
        resp_msg = 'anonymous users not permitted to assign owners'
        asset_group_utils.create_asset_group(
            flask_app_client, None, data.get(), 400, resp_msg
        )
        data.remove_encounter_field(0, 0, 'ownerEmail')

        data.set_field('submitterEmail', 'joe@blogs.com')
        resp = asset_group_utils.create_asset_group(flask_app_client, None, data.get())
        asset_group_uuid = resp.json['guid']
        from app.modules.users.models import User
        import uuid

        assert uuid.UUID(resp.json['owner_guid']) == User.get_public_user().guid

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, staff_user, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)


def test_create_asset_group_detection(
    flask_app, flask_app_client, researcher_1, staff_user, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData
    from tests import utils as test_utils

    orig_objs = test_utils.all_count(db)

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = TestCreationData(transaction_id)
        data.add_filename(0, test_filename)
        data.set_field('speciesDetectionModel', ['someSortOfModel'])

        # Simulate a valid response from Sage but don't actually send the request to Sage
        with mock.patch.object(
            flask_app.acm,
            'request_passthrough_result',
            return_value={'success': True},
        ) as detection_started:
            resp = asset_group_utils.create_asset_group(
                flask_app_client, None, data.get()
            )
            assert detection_started.call_count == 1
            passed_args = detection_started.call_args[0]
            assert passed_args[:-2] == ('job.detect_request', 'post')
            params = passed_args[-2]['params']
            assert set(params.keys()) >= {
                'endpoint',
                'function',
                'jobid',
                'callback_url',
                'image_uuid_list',
                'input',
            }
            assert passed_args[-1] == 'cnn/lightnet'
            asset_group_uuid = resp.json['guid']

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, staff_user, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)
        assert orig_objs == test_utils.all_count(db)


def test_create_bulk_asset_group_dup_asset(flask_app_client, researcher_1, test_root, db):
    # pylint: disable=invalid-name

    transaction_id, test_filename = asset_group_utils.create_bulk_tus_transaction(
        test_root
    )
    asset_group_uuid = None
    try:
        data = asset_group_utils.get_bulk_creation_data(transaction_id, test_filename)
        data.add_filename(0, 'fluke.jpg')
        expected_err = 'found fluke.jpg in multiple sightings'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, expected_err
        )

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)


def test_create_bulk_asset_group(flask_app_client, researcher_1, test_root, db):
    # pylint: disable=invalid-name
    import uuid

    transaction_id, test_filename = asset_group_utils.create_bulk_tus_transaction(
        test_root
    )
    asset_group_uuid = None
    try:
        data = asset_group_utils.get_bulk_creation_data(transaction_id, test_filename)

        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = resp.json['guid']

        assert resp.json['description'] == data.get()['description']
        assert uuid.UUID(resp.json['owner_guid']) == researcher_1.guid
        assets = sorted(resp.json['assets'], key=lambda a: a['filename'])
        asset_guids = [a['guid'] for a in assets]
        assert assets == [
            {
                'filename': 'coelacanth.png',
                'guid': asset_guids[0],
                'src': f'/api/v1/assets/src/{asset_guids[0]}',
            },
            {
                'filename': 'fluke.jpg',
                'guid': asset_guids[1],
                'src': f'/api/v1/assets/src/{asset_guids[1]}',
            },
            {
                'filename': 'phoenix.jpg',
                'guid': asset_guids[2],
                'src': f'/api/v1/assets/src/{asset_guids[2]}',
            },
            {
                'filename': 'zebra.jpg',
                'guid': asset_guids[3],
                'src': f'/api/v1/assets/src/{asset_guids[3]}',
            },
        ]

        # Make sure that the user has the group and it's in the correct state
        user_resp = user_utils.read_user(flask_app_client, researcher_1, 'me')
        assert 'unprocessed_asset_groups' in user_resp.json
        # Not being too rigid in the validation as sporadically '00000000-0000-0000-0000-000000000003'
        # is also in there
        assert asset_group_uuid in user_resp.json['unprocessed_asset_groups']

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)


def test_create_asset_group_simulate_detection(
    flask_app_client, researcher_1, contributor_1, internal_user, test_root, db
):
    # pylint: disable=invalid-name
    import uuid
    from tests.modules.asset_groups.resources.utils import TestCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = TestCreationData(transaction_id)
        data.add_filename(0, test_filename)
        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = resp.json['guid']
        assert 'assets' in resp.json
        assets = resp.json['assets']
        assert len(assets) == 1
        asset_guid = assets[0]['guid']
        assert 'asset_group_sightings' in resp.json
        asset_group_sighting_uuid = resp.json['asset_group_sightings'][0]['guid']
        job_id = str(uuid.uuid4())
        path = f'sighting/{asset_group_sighting_uuid}/sage_detected/{job_id}'
        data = {
            'response': {
                'jobid': job_id,
                'json_result': {
                    'has_assignments': False,
                    'image_uuid_list': [
                        asset_guid,
                    ],
                    'results_list': [
                        [
                            {
                                'class': 'whale_orca+fin_dorsal',
                                'confidence': 0.7909,
                                'height': 820,
                                'id': 947505,
                                'interest': False,
                                'left': 140,
                                'multiple': False,
                                'quality': None,
                                'species': 'whale_orca+fin_dorsal',
                                'theta': 0.0,
                                'top': 0,
                                'uuid': '23b9ac5a-9a52-473a-a4dd-6a1f4f255dbc',
                                'viewpoint': 'left',
                                'width': 1063,
                                'xtl': 140,
                                'ytl': 0,
                            },
                        ],
                    ],
                    'score_list': [
                        0.0,
                    ],
                },
                'status': 'completed',
            },
            'status': {
                'cache': -1,
                'code': 200,
                'message': '',
                'success': True,
            },
        }
        response = asset_group_utils.simulate_detection_response(
            flask_app_client,
            internal_user,
            path,
            data,
            400,
        )
        assert (
            response.json['message']
            == f'AssetGroupSighting {asset_group_sighting_uuid} is not detecting'
        )
        # TODO should fail as AssetGroupSighting is processed so has no jobs outstanding

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        # if sighting_uuid:
        #     import tests.modules.sightings.resources.utils as sighting_utils
        #     sighting_utils.delete_sighting(flask_app_client, researcher_1, asset_group_uuid)
