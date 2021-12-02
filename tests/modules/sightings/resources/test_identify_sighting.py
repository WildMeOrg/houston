# -*- coding: utf-8 -*-
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.utils as test_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(module_unavailable('sightings'), reason='Sightings module disabled')
def test_sighting_identification(
    flask_app,
    flask_app_client,
    researcher_1,
    internal_user,
    test_root,
    db,
    request,
):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting, SightingStage

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

    # Second sighting, the one we'll use for testing, Create with annotation but don't commit.... yet
    (
        asset_group_uuid2,
        asset_group_sighting_guid2,
        asset_uuid2,
    ) = asset_group_utils.create_simple_asset_group(
        flask_app_client, researcher_1, request, test_root
    )
    asset_group_utils.patch_in_dummy_annotation(
        flask_app_client, db, researcher_1, asset_group_sighting_guid2, asset_uuid2
    )

    # Here starts the test for real
    # Create ID config and patch it in
    id_configs = [
        {
            'algorithms': [
                'hotspotter_nosv',
            ],
            'matchingSetDataOwners': 'mine',
        }
    ]
    patch_data = [test_utils.patch_replace_op('idConfigs', id_configs)]
    asset_group_utils.patch_asset_group_sighting(
        flask_app_client,
        researcher_1,
        asset_group_sighting_guid2,
        patch_data,
    )

    # Start ID simulating success response from Sage
    response = asset_group_utils.commit_asset_group_sighting_sage_identification(
        flask_app, flask_app_client, researcher_1, asset_group_sighting_guid2
    )
    sighting_uuid = response.json['guid']

    sighting = Sighting.query.get(sighting_uuid)
    assert sighting.stage == SightingStage.identification

    # Make sure the correct job is created and get ID
    job_uuids = [guid for guid in sighting.jobs.keys()]
    assert len(job_uuids) == 1
    job_uuid = job_uuids[0]
    assert sighting.jobs[job_uuid]['algorithm'] == 'hotspotter_nosv'

    # Simulate response from Sage
    sage_resp = sighting_utils.build_sage_identification_response(
        job_uuid,
        sighting.jobs[job_uuid]['annotation'],
        sighting.jobs[job_uuid]['algorithm'],
    )

    sighting_utils.send_sage_identification_response(
        flask_app_client,
        internal_user,
        sighting_uuid,
        job_uuid,
        sage_resp,
    )
    assert all(not job['active'] for job in sighting.jobs.values())
    assert sighting.stage == SightingStage.un_reviewed
