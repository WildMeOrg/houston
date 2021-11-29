# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import pytest
from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups', 'sightings'), reason='AssetGroups module disabled'
)
def test_ia_pipeline_sim_detect_response(
    flask_app,
    flask_app_client,
    researcher_1,
    regular_user,
    staff_user,
    internal_user,
    test_root,
    db,
    request,
):
    # pylint: disable=invalid-name
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )
    from app.modules.sightings.models import Sighting

    # Use a standard bulk creation data
    creation_data = asset_group_utils.get_bulk_creation_data(
        test_root, request, 'african_terrestrial'
    )

    asset_group_uuid = None
    try:

        # and the sim_sage util to catch it
        resp = asset_group_utils.create_asset_group_sim_sage_init_resp(
            flask_app, flask_app_client, researcher_1, creation_data.get()
        )
        asset_group_uuid = resp.json['guid']
        asset_group_sighting1_guid = resp.json['asset_group_sightings'][0]['guid']

        ags1 = AssetGroupSighting.query.get(asset_group_sighting1_guid)
        assert ags1

        job_uuids = [guid for guid in ags1.jobs.keys()]
        assert len(job_uuids) == 1
        job_uuid = job_uuids[0]
        assert ags1.jobs[job_uuid]['model'] == 'african_terrestrial'

        # Simulate response from Sage
        sage_resp = asset_group_utils.build_sage_detection_response(
            asset_group_sighting1_guid, job_uuid
        )
        asset_group_utils.send_sage_detection_response(
            flask_app_client,
            internal_user,
            asset_group_sighting1_guid,
            job_uuid,
            sage_resp,
        )
        assert ags1.stage == AssetGroupSightingStage.curation

        # commit it (without Identification)
        response = asset_group_utils.commit_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting1_guid
        )
        sighting_uuid = response.json['guid']
        sighting = Sighting.query.get(sighting_uuid)
        encounters = sighting.get_encounters()
        assert len(encounters) == 2

    finally:
        # Restore original state
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
