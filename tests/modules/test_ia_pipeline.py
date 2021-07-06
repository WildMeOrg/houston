# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.extensions.tus.utils as tus_utils


def test_ia_pipeline_sim_detect_response(
    flask_app,
    flask_app_client,
    researcher_1,
    regular_user,
    staff_user,
    internal_user,
    test_root,
    db,
):
    # pylint: disable=invalid-name
    from app.modules.asset_groups.models import (
        AssetGroupSighting,
        AssetGroupSightingStage,
    )
    from app.modules.sightings.models import Sighting

    transaction_id, test_filename = asset_group_utils.create_bulk_tus_transaction(
        test_root
    )
    asset_group_uuid = None
    sighting_uuid = None
    try:
        data = asset_group_utils.get_bulk_creation_data(transaction_id, test_filename)
        # Use a real detection model to trigger a request sent to Sage
        data.set_field('speciesDetectionModel', ['realDetectionModel'])
        # and the sim_sage util to catch it
        resp = asset_group_utils.create_asset_group_sim_sage(
            flask_app, flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = resp.json['guid']
        asset_group_sighting1_guid = resp.json['asset_group_sightings'][0]['guid']

        ags1 = AssetGroupSighting.query.get(asset_group_sighting1_guid)
        assert ags1

        job_uuids = [guid for guid in ags1.jobs.keys()]
        assert len(job_uuids) == 1
        job_uuid = job_uuids[0]
        assert ags1.jobs[job_uuid]['model'] == 'realDetectionModel'

        # Simulate response from Sage
        sage_resp = asset_group_utils.build_sage_detection_response(
            asset_group_uuid, job_uuid
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
        if sighting_uuid:
            sighting_utils.delete_sighting(flask_app_client, staff_user, sighting_uuid)
        tus_utils.cleanup_tus_dir(transaction_id)


# TODO DEX-335 A test that has sage simulated detection and identification
