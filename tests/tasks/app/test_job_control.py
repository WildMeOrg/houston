# -*- coding: utf-8 -*-
import tests.extensions.tus.utils as tus_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.utils as test_utils

import pytest

from tests.utils import (
    module_unavailable,
    extension_unavailable,
    wait_for_elasticsearch_status,
)


# Check that the task methods for the asset control job tasks print the correct output
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_asset_group_detection_jobs(
    flask_app, flask_app_client, researcher_1, staff_user, test_root, db
):
    # pylint: disable=invalid-name
    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = asset_group_utils.AssetGroupCreationData(transaction_id, test_filename)
        data.set_field('speciesDetectionModel', ['african_terrestrial'])

        resp = asset_group_utils.create_asset_group(flask_app_client, None, data.get())
        asset_group_uuid = resp.json['guid']

        progress_guids = []
        for ags in resp.json['asset_group_sightings']:
            progress_guids.append(ags['progress_detection']['guid'])
        test_utils.wait_for_progress(flask_app, progress_guids)

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, staff_user, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(transaction_id)


# Check that the task methods for the sighting job tasks print the correct output
@pytest.mark.skipif(
    module_unavailable('sightings'),
    reason='Sighting module disabled',
)
@pytest.mark.skipif(
    extension_unavailable('elasticsearch'),
    reason='Elasticsearch extension disabled',
)
def test_sighting_identification_jobs(
    flask_app,
    flask_app_client,
    researcher_1,
    test_root,
    db,
    request,
):
    # pylint: disable=invalid-name
    from app.modules.annotations.models import Annotation
    from app.modules.sightings.models import Sighting, SightingStage
    from app.extensions import elasticsearch as es

    if es.is_disabled():
        pytest.skip('Elasticsearch disabled (via command-line)')

    # Create two sightings so that there will be a valid annotation when doing ID for the second one.
    # Otherwise the get_matching_set_data in sightings will return an empty list
    (
        asset_group_uuid1,
        asset_group_sighting_guid1,
        asset_uuid1,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )
    asset_group_utils.patch_in_dummy_annotation(
        flask_app_client, db, researcher_1, asset_group_sighting_guid1, asset_uuid1
    )
    commit_response = asset_group_utils.commit_asset_group_sighting(
        flask_app_client, researcher_1, asset_group_sighting_guid1
    )
    sighting_uuid = commit_response.json['guid']

    # Fake it being all the way though to processed or it won't be valid in the matching set
    sighting = Sighting.query.get(sighting_uuid)
    sighting.stage = SightingStage.processed

    # Second sighting, the one we'll use for testing
    (
        asset_group_uuid2,
        asset_group_sighting_guid2,
        asset_uuid2,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )
    annot_uuid = asset_group_utils.patch_in_dummy_annotation(
        flask_app_client,
        db,
        researcher_1,
        asset_group_sighting_guid2,
        asset_uuid2,
        padding=1,
    )
    response = asset_group_utils.commit_asset_group_sighting_sage_identification(
        flask_app, flask_app_client, researcher_1, asset_group_sighting_guid2
    )
    sighting_uuid = response.json['guid']
    wait_for_elasticsearch_status(flask_app_client, researcher_1)

    sighting = Sighting.query.get(sighting_uuid)
    annotation = Annotation.query.get(annot_uuid)

    jobs = sighting.jobs
    keys = list(jobs.keys())
    key = keys[0]
    job = jobs[key]

    assert job['annotation'] == str(annotation.guid)
    assert job['algorithm'] == 'hotspotter_nosv'
    assert job['matching_set'] is None
    assert job['active']
