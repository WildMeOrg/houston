# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.extensions.tus.utils as tus_utils


# Test a bunch of failure scenarios
def test_create_asset_group(flask_app_client, researcher_1, readonly_user, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)

    try:
        data = TestCreationData(transaction_id, False)
        data.set_field('description', 'This is a test asset_group, please ignore')
        resp_msg = 'bulkUpload field missing from request'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_field('bulkUpload', False)
        resp_msg = 'speciesDetectionModel field missing from request'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )
        data.set_field('speciesDetectionModel', [None])
        resp_msg = 'transactionId field missing from request'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

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
        resp_msg = 'locationId field missing from Sighting 1'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        # Yes, that really is a location, it's a village in Wiltshire
        data.set_sighting_field(0, 'locationId', 'Tiddleywink')
        resp_msg = 'encounters field missing from Sighting 1'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_sighting_field(0, 'encounters', [''])
        resp_msg = 'Encounter 1.1 needs to be a dict'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_sighting_field(0, 'encounters', [{'assetReferences': ''}])
        # data.set_encounter_field(0, 0, 'assetReferences', '')
        resp_msg = 'assetReferences field missing from Encounter 1.1'
        asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get(), 400, resp_msg
        )

        data.set_encounter_field(0, 0, 'assetReferences', [test_filename])
        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )

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
        request_json = metadata_dict.get('frontend_sightings_data')
        assert request_json == data.get()
        asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, resp.json['guid']
        )
    finally:
        tus_utils.cleanup_tus_dir(transaction_id)


def test_create_asset_group_2_assets(flask_app_client, researcher_1, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    tus_utils.prep_tus_dir(test_root, filename='coelacanth.png')
    try:
        data = TestCreationData(transaction_id)
        data.add_filename(0, 0, test_filename)
        data.add_filename(0, 0, 'coelacanth.png')
        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
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
        asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, resp.json['guid']
        )
    finally:
        tus_utils.cleanup_tus_dir(transaction_id)


def test_create_asset_group_anonymous(
    flask_app_client, researcher_1, staff_user, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    try:
        data = TestCreationData(transaction_id)
        data.add_filename(0, 0, test_filename)
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
        from app.modules.users.models import User
        import uuid

        assert uuid.UUID(resp.json['owner_guid']) == User.get_public_user().guid
        asset_group_utils.delete_asset_group(
            flask_app_client, staff_user, resp.json['guid']
        )
    finally:
        tus_utils.cleanup_tus_dir(transaction_id)


def test_create_bulk_asset_group(flask_app_client, researcher_1, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData
    import uuid

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    tus_utils.prep_tus_dir(test_root, filename='coelacanth.png')
    tus_utils.prep_tus_dir(test_root, filename='fluke.jpg')
    tus_utils.prep_tus_dir(test_root, filename='phoenix.jpg')

    try:
        data = TestCreationData(transaction_id)
        data.add_filename(0, 0, test_filename)
        data.add_encounter(0)
        data.add_filename(0, 1, 'fluke.jpg')
        data.add_sighting('Hogpits Bottom')
        data.add_encounter(1)
        data.add_filename(1, 0, 'coelacanth.png')
        data.add_encounter(1)
        data.add_filename(1, 1, 'fluke.jpg')
        data.add_filename(1, 1, 'phoenix.jpg')
        data.set_field('bulkUpload', True)

        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
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

        asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, resp.json['guid']
        )
    finally:
        tus_utils.cleanup_tus_dir(transaction_id)
