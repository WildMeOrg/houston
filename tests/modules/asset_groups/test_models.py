# -*- coding: utf-8 -*-
import datetime
from unittest import mock
import uuid
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.utils as test_utils
import pytest

from tests.utils import module_unavailable, extension_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_asset_group_sightings_jobs(flask_app, db, admin_user, test_root, request):
    from app.modules.asset_groups.models import (
        AssetGroup,
        AssetGroupSighting,
        AssetGroupSightingStage,
    )
    from tests.utils import copy_uploaded_file, create_transaction_dir

    input_filename = 'zippy'
    transaction_id = str(uuid.uuid4())
    trans_dir = create_transaction_dir(flask_app, transaction_id)
    copy_uploaded_file(test_root, input_filename, trans_dir, input_filename)

    asset_group = AssetGroup.create_from_tus(
        'test asset group description', admin_user, transaction_id, paths=[input_filename]
    )
    asset_group.config['speciesDetectionModel'] = test_utils.dummy_detection_info()
    # Make sure config changes are saved
    asset_group.config = asset_group.config
    with db.session.begin():
        db.session.add(asset_group)
    request.addfinalizer(asset_group.delete)
    sighting_config1 = test_utils.dummy_sighting_info()
    sighting_config1['assetReferences'] = [input_filename]
    ags1 = AssetGroupSighting(
        asset_group=asset_group,
        sighting_config=sighting_config1,
        detection_configs=['african_terrestrial'],
    )
    assert ags1.stage == AssetGroupSightingStage.detection
    assert ags1.get_detection_start_time() == ags1.created.isoformat() + 'Z'
    assert ags1.get_curation_start_time() is None
    sighting_config2 = test_utils.dummy_sighting_info()
    sighting_config2['assetReferences'] = []
    ags2 = AssetGroupSighting(
        asset_group=asset_group,
        sighting_config=sighting_config2,
        detection_configs=test_utils.dummy_detection_info(),
    )
    # no assets => processed
    assert ags2.stage == AssetGroupSightingStage.processed
    assert ags2.get_detection_start_time() is None
    assert ags2.get_curation_start_time() is None

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


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_asset_group_sightings_bulk(
    flask_app, flask_app_client, db, admin_user, researcher_1, test_root, request
):
    from app.modules.asset_groups.models import AssetGroupSighting

    asset_group_uuid = None
    try:
        data = asset_group_utils.get_bulk_creation_data(test_root, request)
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


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_asset_group_sighting_get_completion(
    flask_app, flask_app_client, researcher_1, test_root, request
):
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )

    # Use a real detection model to trigger a request sent to Sage
    data = asset_group_utils.get_bulk_creation_data(
        test_root, request, 'african_terrestrial'
    )

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
    detection_time = asset_group_sighting.created.isoformat() + 'Z'
    assert asset_group_sighting.get_detection_start_time() == detection_time
    assert asset_group_sighting.get_curation_start_time() is None
    assert asset_group_sighting.get_completion() == 0
    # Mark job as completed -> "curation" stage
    asset_group_sighting.job_complete(list(asset_group_sighting.jobs.keys())[0])
    assert all(not job['active'] for job in asset_group_sighting.jobs.values())
    assert asset_group_sighting.stage == AssetGroupSightingStage.curation
    assert asset_group_sighting.get_detection_start_time() == detection_time
    curation_time = asset_group_sighting.curation_start.isoformat() + 'Z'
    assert asset_group_sighting.get_curation_start_time() == curation_time
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
        asset_group_sighting.commit()
    assert asset_group_sighting.stage == AssetGroupSightingStage.processed
    assert asset_group_sighting.get_detection_start_time() == detection_time
    assert asset_group_sighting.get_curation_start_time() == curation_time
    assert asset_group_sighting.get_completion() == 30

    # Check unknown and failed by manually setting them
    asset_group_sighting.stage = AssetGroupSightingStage.unknown
    assert asset_group_sighting.get_completion() == 0

    asset_group_sighting.stage = AssetGroupSightingStage.failed
    assert asset_group_sighting.get_completion() == 100


@pytest.mark.skipif(extension_unavailable('edm'), reason='EDM extension disabled')
def test_asset_group_sighting_config_field_getter(researcher_1, request):
    from app.modules.asset_groups.models import AssetGroupSighting, AssetGroup

    asset_group = AssetGroup(owner=researcher_1)
    request.addfinalizer(asset_group.delete)
    ags = AssetGroupSighting(
        asset_group=asset_group,
        sighting_config=test_utils.dummy_sighting_info(),
        detection_configs=test_utils.dummy_detection_info(),
    )
    request.addfinalizer(ags.delete)

    config_field_getter = AssetGroupSighting.config_field_getter

    ags.config = None
    assert config_field_getter('name')(ags) is None
    assert config_field_getter('name', default='value')(ags) == 'value'
    assert config_field_getter('name', default=1, cast=int)(ags) == 1
    assert config_field_getter('name', cast=int)(ags) is None

    ags.config = {'id': '10', 'decimalLatitude': None}
    assert config_field_getter('id')(ags) == '10'
    assert config_field_getter('id', default=1)(ags) == '10'
    assert config_field_getter('id', default=1, cast=int)(ags) == 10
    assert config_field_getter('id', cast=int)(ags) == 10

    assert config_field_getter('decimalLatitude')(ags) is None
    assert config_field_getter('decimalLatitude', default=1.0)(ags) == 1.0
    assert config_field_getter('decimalLatitude', default=1.0, cast=float)(ags) == 1.0
    assert config_field_getter('decimalLatitude', cast=float)(ags) is None

    assert config_field_getter('name')(ags) is None
    assert config_field_getter('name', default='value')(ags) == 'value'
    assert config_field_getter('name', default=1, cast=int)(ags) == 1
    assert config_field_getter('name', cast=int)(ags) is None
