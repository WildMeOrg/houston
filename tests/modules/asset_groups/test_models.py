# -*- coding: utf-8 -*-
import uuid

import pytest

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.utils as test_utils
from app.utils import HoustonException
from tests.utils import module_unavailable


def ensure_encounter_guids(db, ags):
    for encounter_num in range(len(ags.sighting_config['encounters'])):
        if 'guid' not in ags.sighting_config['encounters'][encounter_num]:
            with db.session.begin(subtransactions=True):
                ags.sighting_config['encounters'][encounter_num]['guid'] = str(
                    uuid.uuid4()
                )
                # sighting_config is actually an alias, need to rewrite the top level DB item
                ags.config = ags.config
                db.session.merge(ags)
                db.session.refresh(ags)


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_asset_group_sightings_jobs(flask_app, db, admin_user, test_root, request):
    from app.modules.asset_groups.models import (
        AssetGroup,
        AssetGroupSighting,
        AssetGroupSightingStage,
    )
    from app.modules.progress.models import Progress, ProgressStatus
    from tests.utils import copy_uploaded_file, create_transaction_dir

    input_filename = 'zippy'
    transaction_id = str(uuid.uuid4())
    trans_dir = create_transaction_dir(flask_app, transaction_id)
    copy_uploaded_file(test_root, input_filename, trans_dir, input_filename)

    asset_group, _ = AssetGroup.create_from_tus(
        'test asset group description',
        admin_user,
        transaction_id,
        paths=[input_filename],
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
    ags1.setup()
    assert ags1.stage == AssetGroupSightingStage.detection
    assert ags1.get_detection_start_time() == ags1.detection_start.isoformat() + 'Z'
    assert ags1.get_curation_start_time() is None
    sighting_config2 = test_utils.dummy_sighting_info()
    sighting_config2['assetReferences'] = []
    ags2 = AssetGroupSighting(
        asset_group=asset_group,
        sighting_config=sighting_config2,
        detection_configs=test_utils.dummy_detection_info(),
    )
    ags2.setup()

    # no assets => processed
    assert ags2.stage == AssetGroupSightingStage.processed
    # Need to ensure all encounters in ags's have guids. The real operation of the code does this itself but as
    # this test pokes bits of the object randomly, it needs to be done here.
    ensure_encounter_guids(db, ags1)
    ensure_encounter_guids(db, ags2)

    assert ags2.get_detection_start_time() is None
    assert ags2.get_curation_start_time() is not None

    progress_guids = [str(ags1.progress_detection.guid)]
    test_utils.wait_for_progress(flask_app, progress_guids)

    ags1.init_progress_detection(overwrite=True)
    ags1.send_detection_to_sage('african_terrestrial')

    with pytest.raises(HoustonException) as exc:
        ags2.send_detection_to_sage('african_terrestrial')
    assert (
        str(exc.value)
        == 'Cannot rerun detection on AssetGroupSighting in processed stage'
    )

    progress_guids = [str(ags1.progress_detection.guid)]
    test_utils.wait_for_progress(flask_app, progress_guids)

    keys = list(ags1.jobs.keys())
    key = keys[0]
    job = ags1.jobs[key]
    assert job['model'] == 'african_terrestrial'
    assert not job['active']
    assert job['asset_guids'] == [str(asset_group.assets[0].guid)]

    # not exactly sure why this is None, but we need it not-None
    ags1.asset_group.config['speciesDetectionModel'] = ['fubar']
    ags1.asset_group.config = ags1.asset_group.config
    ps = ags1.get_pipeline_status()
    assert ps['detection']
    assert not ps['detection']['inProgress']
    assert not ps['detection']['failed']

    curation_progress = {
        'skipped': False,
        'start': ags1.get_curation_start_time(),
        'end': None,
        'inProgress': True,
        'complete': False,
        'failed': False,
        'progress': 0.5,
        'ahead': None,
        'eta': None,
        'message': None,
        'description': None,
        'status': None,
        'steps': 0,
        'stepsComplete': 0,
    }
    assert ps['curation'] == curation_progress

    # some additional testing for coverage
    ags1.progress_preparation.status = ProgressStatus.skipped
    ps = ags1.get_pipeline_status()
    assert ps['preparation']['skipped']
    ags1.progress_preparation.status = ProgressStatus.failed
    ps = ags1.get_pipeline_status()
    assert ps['preparation']['failed']
    ags1.progress_preparation.status = ProgressStatus.created
    ps = ags1.get_pipeline_status()
    assert ps['preparation']['inProgress']

    ags1.progress_detection.status = ProgressStatus.skipped
    ps = ags1.get_pipeline_status()
    assert ps['detection']['skipped']
    ags1.progress_detection.status = ProgressStatus.failed
    ps = ags1.get_pipeline_status()
    assert ps['detection']['failed']
    ags1.progress_detection.status = ProgressStatus.created
    ps = ags1.get_pipeline_status()
    assert ps['detection']['inProgress']

    ags1.progress_identification = Progress(description='Test')
    with db.session.begin():
        db.session.add(ags1.progress_identification)
    ags1.progress_identification.status = ProgressStatus.skipped
    ps = ags1.get_pipeline_status()
    assert ps['identification']['skipped']
    ags1.progress_identification.status = ProgressStatus.failed
    ps = ags1.get_pipeline_status()
    assert ps['identification']['failed']
    ags1.progress_identification.status = ProgressStatus.created
    ps = ags1.get_pipeline_status()
    assert ps['identification']['inProgress']


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
        assert sorted(
            ags.config['sighting']['locationId'] for ags in (ags1, ags2)
        ) == sorted(cnf['locationId'] for cnf in data.content['sightings'])

    finally:
        # Restore original state
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_asset_group_sighting_config_field_getter(researcher_1, request):
    from app.modules.asset_groups.models import AssetGroup, AssetGroupSighting

    asset_group = AssetGroup(owner=researcher_1)
    request.addfinalizer(asset_group.delete)
    ags = AssetGroupSighting(
        asset_group=asset_group,
        sighting_config=test_utils.dummy_sighting_info(),
        detection_configs=test_utils.dummy_detection_info(),
    )
    ags.setup()
    request.addfinalizer(ags.delete)

    config_field_getter = AssetGroupSighting.config_field_getter

    ags.sighting_config = None
    assert config_field_getter('name')(ags) is None
    assert config_field_getter('name', default='value')(ags) == 'value'
    assert config_field_getter('name', default=1, cast=int)(ags) == 1
    assert config_field_getter('name', cast=int)(ags) is None

    ags.sighting_config = {'id': '10', 'decimalLatitude': None}
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
