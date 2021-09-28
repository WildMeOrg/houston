# -*- coding: utf-8 -*-
import datetime
import pathlib
from unittest import mock
import uuid
import tests.extensions.tus.utils as tus_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils


def test_asset_group_sightings_jobs(flask_app, db, admin_user, test_root, request):
    from app.modules.asset_groups.models import AssetGroup, AssetGroupSighting

    transaction_id = str(uuid.uuid4())
    trans_dir = (
        pathlib.Path(flask_app.config['UPLOADS_DATABASE_PATH'])
        / f'trans-{transaction_id}'
    )
    trans_dir.mkdir(parents=True)
    with (trans_dir / 'zebra.jpg').open('wb') as f:
        with (test_root / 'zebra.jpg').open('rb') as g:
            f.write(g.read())
    asset_group = AssetGroup.create_from_tus(
        'test asset group description', admin_user, transaction_id
    )
    with db.session.begin():
        db.session.add(asset_group)
    request.addfinalizer(asset_group.delete)

    ags1 = AssetGroupSighting(
        config={'assetReferences': ['zebra.jpg']}, asset_group_guid=asset_group.guid
    )
    ags2 = AssetGroupSighting(
        config={'assetReferences': []}, asset_group_guid=asset_group.guid
    )
    with db.session.begin():
        db.session.add(ags1)
        db.session.add(ags2)
    request.addfinalizer(ags1.delete)
    request.addfinalizer(ags2.delete)

    now = datetime.datetime(2021, 7, 7, 17, 55, 34)
    job_id1 = uuid.UUID('53ea04e0-1e87-412d-aa17-0ff5e05db78d')
    job_id2 = uuid.UUID('fca55971-f014-4a8d-9e94-2c88b72d2d8c')

    uuids = [job_id2, job_id1]

    from app.modules.asset_groups.tasks import sage_detection

    # Don't send anything to acm
    with mock.patch('app.modules.asset_groups.models.current_app') as mock_app:
        mock_app.config.get.return_value = 'zebra'
        with mock.patch('datetime.datetime') as mock_datetime:
            with mock.patch(
                'app.modules.asset_groups.models.uuid.uuid4', side_effect=uuids.pop
            ):
                mock_datetime.utcnow.return_value = now
                sage_detection(str(ags1.guid), 'african_terrestrial')
                sage_detection(str(ags2.guid), 'african_terrestrial')

    assert AssetGroupSighting.query.get(ags1.guid).jobs == {
        str(job_id1): {
            'model': 'african_terrestrial',
            'active': True,
            'start': now,
            'asset_ids': [str(asset_group.assets[0].guid)],
        },
    }
    assert AssetGroupSighting.query.get(ags2.guid).jobs == {
        str(job_id2): {
            'model': 'african_terrestrial',
            'active': True,
            'start': now,
            'asset_ids': [],
        },
    }


def test_asset_group_sightings_bulk(
    flask_app, flask_app_client, db, admin_user, researcher_1, test_root, request
):
    from app.modules.asset_groups.models import AssetGroupSighting

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

        # Make sure that both AGS' are created and have the correct locations
        ags1 = AssetGroupSighting.query.get(resp.json['asset_group_sightings'][0]['guid'])
        ags2 = AssetGroupSighting.query.get(resp.json['asset_group_sightings'][1]['guid'])
        assert ags1
        assert ags2

        # Due to DB interactions, cannot rely on the order
        assert sorted(ags.config['locationId'] for ags in (ags1, ags2)) == sorted(
            cnf['locationId'] for cnf in data.content['sightings']
        )

    finally:
        # Restore original state
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )

        tus_utils.cleanup_tus_dir(transaction_id)


def test_asset_group_sighting_get_completion(
    flask_app, flask_app_client, researcher_1, test_root, request
):
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )

    # Create asset group sighting
    transaction_id, test_filename = asset_group_utils.create_bulk_tus_transaction(
        test_root
    )
    data = asset_group_utils.get_bulk_creation_data(transaction_id, test_filename)
    # Use a real detection model to trigger a request sent to Sage
    data.set_field('speciesDetectionModel', ['african_terrestrial'])
    # and the sim_sage util to catch it
    resp = asset_group_utils.create_asset_group_sim_sage_init_resp(
        flask_app, flask_app_client, researcher_1, data.get()
    )
    asset_group_guid = resp.json['guid']
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, asset_group_guid
        )
    )

    # Check get_completion()
    asset_group_sighting_guid = resp.json['asset_group_sightings'][0]['guid']
    asset_group_sighting = AssetGroupSighting.query.get(asset_group_sighting_guid)
    # In "detection" stage
    assert asset_group_sighting.stage == AssetGroupSightingStage.detection
    assert asset_group_sighting.get_completion() == 0
    # Mark job as completed -> "curation" stage
    asset_group_sighting.job_complete(list(asset_group_sighting.jobs.keys())[0])
    assert all(not job['active'] for job in asset_group_sighting.jobs.values())
    assert asset_group_sighting.stage == AssetGroupSightingStage.curation
    assert asset_group_sighting.get_completion() == 10

    # Call commit to move to "processed" stage
    with mock.patch(
        'app.modules.asset_groups.models.current_app.edm.request_passthrough_result',
        return_value={
            'id': str(uuid.uuid4()),
            'encounters': [
                {'id': str(uuid.uuid4())},
                {'id': str(uuid.uuid4())},
            ],
        },
    ):
        sighting = asset_group_sighting.commit()
    request.addfinalizer(sighting.delete_cascade)
    assert asset_group_sighting.stage == AssetGroupSightingStage.processed
    assert asset_group_sighting.get_completion() == 76

    # Check unknown and failed by manually setting them
    asset_group_sighting.stage = AssetGroupSightingStage.unknown
    assert asset_group_sighting.get_completion() == 0

    asset_group_sighting.stage = AssetGroupSightingStage.failed
    assert asset_group_sighting.get_completion() == 100
