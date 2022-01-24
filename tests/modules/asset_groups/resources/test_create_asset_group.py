# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.users.resources.utils as user_utils
import tests.extensions.tus.utils as tus_utils
import json
from unittest import mock
import pytest

from tests.utils import (
    module_unavailable,
    random_decimal_latitude,
    random_decimal_longitude,
)


# Test a bunch of failure scenarios
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_asset_group(flask_app_client, researcher_1, readonly_user, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import AssetGroupCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None

    try:
        data = AssetGroupCreationData(transaction_id, populate_default=False)
        data.set_field('uploadType', 'form')
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
        data.set_field('sightings', [{}])
        resp_msg = 'time field missing from Sighting 1'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )
        data.set_sighting_field(0, 'time', 'never')

        resp_msg = 'timeSpecificity field missing from Sighting 1'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )
        data.set_sighting_field(0, 'timeSpecificity', 'time')

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
        data.remove_field('uploadType')
        resp_msg = 'uploadType field missing from request'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_field('uploadType', 'form')
        resp_msg = 'Need either locationID or GPS data in Sighting 1'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_sighting_field(0, 'decimalLatitude', random_decimal_latitude())
        data.set_sighting_field(0, 'decimalLongitude', random_decimal_longitude())
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

        # Basic checking that AGS data is valid
        assert len(resp.json['asset_group_sightings']) == 1
        ags = resp.json['asset_group_sightings'][0]
        assert ags['asset_group_guid'] == asset_group_uuid
        assert ags['stage'] == 'curation'
        assert ags['creator']['guid'] == str(researcher_1.guid)
        assert ags['detection_start_time'] is None
        assert ags['curation_start_time'] is not None

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_asset_group_2_assets(flask_app_client, researcher_1, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import AssetGroupCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    tus_utils.prep_tus_dir(test_root, filename='coelacanth.png')
    asset_group_uuid = None
    try:
        data = AssetGroupCreationData(transaction_id, test_filename)
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


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_asset_group_no_assets(
    flask_app_client, researcher_1, contributor_1, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import AssetGroupCreationData

    asset_group_uuid = None
    try:
        data = AssetGroupCreationData(None)
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
        assert len(resp.json['asset_group_sightings']) == 1
        ags = resp.json['asset_group_sightings'][0]
        assert ags['sighting_guid'] is not None
        assert ags['stage'] == 'processed'
        assert ags['curation_start_time'] is None
        assert ags['detection_start_time'] is None

        # Make sure that the user has a single unprocessed sighting
        user_resp = user_utils.read_user(flask_app_client, researcher_1, 'me')
        assert 'unprocessed_sightings' in user_resp.json
        assert len(user_resp.json['unprocessed_sightings']) == 1
    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_asset_group_anonymous(
    flask_app_client, researcher_1, staff_user, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import AssetGroupCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = AssetGroupCreationData(transaction_id, test_filename)
        data.set_field('submitterEmail', researcher_1.email)
        resp_msg = 'Invalid submitter data'
        asset_group_utils.create_asset_group(
            flask_app_client, None, data.get(), 403, resp_msg
        )
        data.remove_field('submitterEmail')

        data.set_field('uploadType', 'bulk')
        resp_msg = 'anonymous users not permitted to do bulk upload'
        asset_group_utils.create_asset_group(
            flask_app_client, None, data.get(), 400, resp_msg
        )
        data.set_field('uploadType', 'form')

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


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def no_test_create_asset_group_detection(
    flask_app, flask_app_client, researcher_1, staff_user, test_root, db, request
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import AssetGroupCreationData
    from time import sleep

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)

    data = AssetGroupCreationData(transaction_id, test_filename)
    data.set_field('speciesDetectionModel', ['african_terrestrial'])
    resp = asset_group_utils.create_asset_group(
        flask_app_client, researcher_1, data.get()
    )
    assert set(resp.json.keys()) >= {'guid', 'asset_group_sightings'}
    asset_group_uuid = resp.json['guid']
    asset_group_sightings = resp.json['asset_group_sightings']
    assert len(asset_group_sightings) == 1
    asset_group_sighting_uuid = asset_group_sightings[0]['guid']
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, staff_user, asset_group_uuid
        )
    )

    # Request has gone to Sage, or should have
    asset_group_sightings = resp.json['asset_group_sightings']
    assert len(asset_group_sightings) == 1
    asset_group_sighting_uuid = asset_group_sightings[0]['guid']
    read_resp = asset_group_utils.read_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_uuid
    )
    while read_resp.json['stage'] == 'detection':
        sleep(5)
        read_resp = asset_group_utils.read_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_uuid
        )


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_asset_group_sim_detection(
    flask_app, flask_app_client, researcher_1, staff_user, internal_user, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import AssetGroupCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = AssetGroupCreationData(transaction_id, test_filename)
        data.set_field('speciesDetectionModel', ['african_terrestrial'])

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
                'jobid',
                'callback_url',
                'image_uuid_list',
                'input',
            }
            assert passed_args[-1] == 'cnn/lightnet'

            job_id = params['jobid']
            assert set(resp.json.keys()) >= {'guid', 'asset_group_sightings', 'assets'}
            asset_group_sighting_uuid = resp.json['asset_group_sightings'][0]['guid']
            asset_group_uuid = resp.json['guid']
            assets = sorted(resp.json['assets'], key=lambda a: a['filename'])
            assert len(assets) == 1
            asset_guids = [a['guid'] for a in assets]

        asset_group_utils.simulate_job_detection_response(
            flask_app_client,
            internal_user,
            asset_group_sighting_uuid,
            asset_guids[0],
            job_id,
        )
        read_resp = asset_group_utils.read_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_uuid
        )
        assert read_resp.json['stage'] == 'curation'
    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, staff_user, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_asset_group_repeat_detection(
    flask_app,
    flask_app_client,
    researcher_1,
    internal_user,
    staff_user,
    test_root,
    db,
    request,
):
    import tests.modules.assets.resources.utils as asset_utils
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )

    asset_group_uuid = None
    data = asset_group_utils.get_bulk_creation_data(test_root, request)
    # Use a real detection model to trigger a request sent to Sage
    data.set_field('speciesDetectionModel', ['african_terrestrial'])

    # and the sim_sage util to catch it
    resp = asset_group_utils.create_asset_group_sim_sage_init_resp(
        flask_app, flask_app_client, researcher_1, data.get()
    )
    asset_group_uuid = resp.json['guid']
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, asset_group_uuid
        )
    )
    asset_group_sighting1_guid = resp.json['asset_group_sightings'][0]['guid']

    ags1 = AssetGroupSighting.query.get(asset_group_sighting1_guid)
    assert ags1

    job_uuids = [guid for guid in ags1.jobs.keys()]
    assert len(job_uuids) == 1
    job_uuid = job_uuids[0]
    assert ags1.jobs[job_uuid]['model'] == 'african_terrestrial'

    # Simulate response from Sage
    asset_group_utils.send_sage_detection_response(
        flask_app_client,
        internal_user,
        asset_group_sighting1_guid,
        job_uuid,
    )
    assert ags1.stage == AssetGroupSightingStage.curation

    # Rotate one of the assets
    from app.modules.annotations.models import Annotation

    annot = Annotation.query.filter_by(
        content_guid=asset_group_utils.ANNOTATION_UUIDS[0]
    ).first()
    asset_guid = annot.asset.guid

    patch_data = [
        {
            'op': 'replace',
            'path': '/image',
            'value': {'rotate': {'angle': 45}},
        },
    ]
    asset_utils.patch_asset(flask_app_client, asset_guid, researcher_1, patch_data)

    # Simulate a valid response from Sage but don't actually send the request to Sage
    from app.modules.asset_groups import tasks

    with mock.patch.object(
        flask_app.acm,
        'request_passthrough_result',
        return_value={'success': True},
    ) as detection_reran:

        with mock.patch.object(
            tasks.sage_detection,
            'delay',
            side_effect=lambda *args, **kwargs: tasks.sage_detection(*args, **kwargs),
        ):
            asset_group_utils.detect_asset_group_sighting(
                flask_app_client, researcher_1, asset_group_sighting1_guid
            )
        assert detection_reran.call_count == 1
        passed_args = detection_reran.call_args[0]
        assert passed_args[:-2] == ('job.detect_request', 'post')
        params = passed_args[-2]['params']
        assert set(params.keys()) >= {
            'endpoint',
            'jobid',
            'callback_url',
            'image_uuid_list',
            'input',
        }
        assert params['image_uuid_list'] == json.dumps(
            [f'houston+http://houston:5000/api/v1/assets/src_raw/{asset_guid}']
        )
        job_uuid = params['jobid']
        assert ags1.stage == AssetGroupSightingStage.detection
        # Simulate response from Sage
        asset_group_utils.send_sage_detection_response(
            flask_app_client,
            internal_user,
            asset_group_sighting1_guid,
            job_uuid,
        )
        assert ags1.stage == AssetGroupSightingStage.curation


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_bulk_asset_group_dup_asset(
    flask_app_client, researcher_1, test_root, db, request
):
    # pylint: disable=invalid-name

    data = asset_group_utils.get_bulk_creation_data(test_root, request)
    data.add_filename(0, 'fluke.jpg')
    expected_err = 'found fluke.jpg in multiple sightings'
    asset_group_utils.create_asset_group(
        flask_app_client, researcher_1, data.get(), 400, expected_err
    )


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_bulk_asset_group(flask_app_client, researcher_1, test_root, db, request):
    # pylint: disable=invalid-name
    import uuid

    asset_group_uuid = None
    try:
        data = asset_group_utils.get_bulk_creation_data(test_root, request)

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
        group_data = [
            group
            for group in user_resp.json['unprocessed_asset_groups']
            if group['uuid'] == asset_group_uuid
        ]
        assert len(group_data) == 1
        assert group_data[0]['uploadType'] == 'bulk'

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_asset_group_individual(
    flask_app_client,
    researcher_1,
    staff_user,
    test_root,
    db,
    empty_individual,
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import AssetGroupCreationData
    import uuid

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = AssetGroupCreationData(transaction_id, test_filename)
        dummy_uuid = str(uuid.uuid4())
        data.set_encounter_field(0, 0, 'individualUuid', dummy_uuid)
        resp_msg = f'Encounter 1.1 individual {dummy_uuid} not found'
        asset_group_utils.create_asset_group(
            flask_app_client, None, data.get(), 400, resp_msg
        )
        with db.session.begin():
            db.session.add(empty_individual)
        data.set_encounter_field(0, 0, 'individualUuid', str(empty_individual.guid))

        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = resp.json['guid']

    finally:
        with db.session.begin():
            db.session.delete(empty_individual)
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, staff_user, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_delete_asset_group_sighting(test_root, flask_app_client, researcher_1, request):
    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    data = asset_group_utils.AssetGroupCreationData(transaction_id, test_filename)
    # Create asset group with 1 sighting
    resp = asset_group_utils.create_asset_group(
        flask_app_client, researcher_1, data.get()
    )
    ag_guid = resp.json['guid']
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, ag_guid
        )
    )

    # Delete the only asset group sighting deletes the asset group
    ags_guid = resp.json['asset_group_sightings'][0]['guid']
    with flask_app_client.login(
        researcher_1, auth_scopes=('asset_group_sightings:write',)
    ):
        resp = flask_app_client.get(
            f'/api/v1/asset_groups/sighting/as_sighting/{ags_guid}'
        )
        assert resp.status_code == 200
        resp = flask_app_client.delete(
            f'/api/v1/asset_groups/sighting/as_sighting/{ags_guid}'
        )
        assert resp.status_code == 204
        resp = flask_app_client.get(
            f'/api/v1/asset_groups/sighting/as_sighting/{ags_guid}'
        )
        assert resp.status_code == 404
    asset_group_utils.read_asset_group(
        flask_app_client, researcher_1, ag_guid, expected_status_code=404
    )

    # Create asset group with 2 sightings
    data = asset_group_utils.get_bulk_creation_data(test_root, request)
    resp = asset_group_utils.create_asset_group(
        flask_app_client, researcher_1, data.get()
    )
    ag_guid = resp.json['guid']
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, ag_guid
        )
    )

    # Delete one of the asset group sightings
    ags_guids = [a['guid'] for a in resp.json['asset_group_sightings']]
    with flask_app_client.login(
        researcher_1, auth_scopes=('asset_group_sightings:write',)
    ):
        resp = flask_app_client.get(
            f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[0]}'
        )
        assert resp.status_code == 200
        resp = flask_app_client.delete(
            f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[0]}'
        )
        assert resp.status_code == 204
        resp = flask_app_client.get(
            f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[0]}'
        )
        assert resp.status_code == 404
        # Check the other asset group sighting still exist
        resp = flask_app_client.get(
            f'/api/v1/asset_groups/sighting/as_sighting/{ags_guids[1]}'
        )
        assert resp.status_code == 200
    # Check asset group still exists
    asset_group_utils.read_asset_group(flask_app_client, researcher_1, ag_guid)
