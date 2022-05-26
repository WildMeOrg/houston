# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

import tests.modules.annotations.resources.utils as annot_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.assets.resources.utils as asset_utils
import tests.modules.encounters.resources.utils as enc_utils
import tests.modules.sightings.resources.utils as sighting_utils
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
    description = 'International names Þröstur Sélène cédric characters &%$* ¼ ©,® ™ m².'
    location = 'Montréal'
    creation_data.set_field('description', description)
    creation_data.set_sighting_field(0, 'verbatimLocality', location)
    creation_data.set_encounter_field(0, 0, 'verbatimLocality', location)

    asset_group_uuid = None
    try:
        # and the sim_sage util to catch it
        ag_resp = asset_group_utils.create_asset_group_sim_sage_init_resp(
            flask_app, flask_app_client, researcher_1, creation_data.get()
        )
        asset_group_uuid = ag_resp.json['guid']
        asset_group_sighting1_guid = ag_resp.json['asset_group_sightings'][0]['guid']

        ags1 = AssetGroupSighting.query.get(asset_group_sighting1_guid)
        assert ags1

        ags_as_sighting = asset_group_utils.read_asset_group_sighting_as_sighting(
            flask_app_client, researcher_1, asset_group_sighting1_guid
        )
        assert ags_as_sighting.json['speciesDetectionModel'] == ['african_terrestrial']

        job_uuids = [guid for guid in ags1.jobs.keys()]
        assert len(job_uuids) == 1
        job_uuid = job_uuids[0]
        assert ags1.jobs[job_uuid]['model'] == 'african_terrestrial'

        # Simulate response from Sage
        assert ags1.stage == AssetGroupSightingStage.curation

        # manually add annots to encounters
        ags_as_sighting = asset_group_utils.read_asset_group_sighting_as_sighting(
            flask_app_client, researcher_1, asset_group_sighting1_guid
        )
        annots = []
        for asset in ags_as_sighting.json['assets']:
            annots += asset['annotations']

        annot_guids = [annot['guid'] for annot in annots]
        encounter_guids = [enc['guid'] for enc in ags_as_sighting.json['encounters']]

        asset_group_utils.patch_in_annotations(
            flask_app_client,
            researcher_1,
            asset_group_sighting1_guid,
            encounter_guids[0],
            annot_guids,
        )
        ags_as_sighting = asset_group_utils.read_asset_group_sighting_as_sighting(
            flask_app_client, researcher_1, asset_group_sighting1_guid
        )

        # Make sure the patch worked
        for enc in ags_as_sighting.json['encounters']:
            for ann in enc.get('annotations', []):
                assert ann['encounter_guid'] == enc['guid']

        # commit it (without Identification)
        response = asset_group_utils.commit_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting1_guid
        )
        sighting_uuid = response.json['guid']
        sighting = Sighting.query.get(sighting_uuid)
        encounters = sighting.get_encounters()
        assert len(encounters) == 2

        sighting_resp = sighting_utils.read_sighting(
            flask_app_client, researcher_1, sighting_uuid
        )
        assert sighting_resp.json['speciesDetectionModel'] == ['african_terrestrial']
        sighting_enc_guids = [enc['guid'] for enc in sighting_resp.json['encounters']]
        # Deliberately do not test the entire contents of the debug output.
        # This is fluid and for our debug only
        asset_group_utils.read_asset_group(
            flask_app_client, staff_user, f'debug/{asset_group_uuid}'
        )
        asset_group_utils.read_asset_group_sighting_debug(
            flask_app_client, staff_user, asset_group_sighting1_guid
        )
        sighting_utils.read_sighting_path(
            flask_app_client, staff_user, f'debug/{sighting_uuid}'
        )
        enc_debug = enc_utils.read_encounter_debug(
            flask_app_client, staff_user, sighting_enc_guids[0]
        )
        assert enc_debug.json['guid'] == sighting_uuid
        annot_guids = []
        for enc in sighting_resp.json['encounters']:
            for annot in enc['annotations']:
                annot_guids.append(annot['guid'])

        if len(annot_guids) > 0:
            annot_debug = annot_utils.read_debug(
                flask_app_client, staff_user, annot_guids[0]
            )
            assert annot_debug.json['guid'] == sighting_uuid

        asset_guids = [asset['guid'] for asset in ag_resp.json['assets']]
        asset_debug = asset_utils.read_asset(
            flask_app_client, staff_user, f'debug/{asset_guids[0]}'
        ).json
        assert asset_debug['git_store']['guid'] == asset_group_uuid

    finally:
        # Restore original state
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
