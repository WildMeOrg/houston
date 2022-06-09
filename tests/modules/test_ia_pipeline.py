# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import pytest

import tests.modules.annotations.resources.utils as annot_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.assets.resources.utils as asset_utils
import tests.modules.encounters.resources.utils as enc_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.modules.site_settings.resources.utils as site_setting_utils
from tests import utils as test_utils
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
            ).json
            assert annot_debug['sighting']['guid'] == sighting_uuid

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


@pytest.mark.skipif(
    module_unavailable('asset_groups', 'sightings'), reason='AssetGroups module disabled'
)
def test_ia_pipeline_conf_id(
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
    regions = site_setting_utils.get_and_ensure_test_regions(flask_app_client, staff_user)
    region1_id = regions[0]['id']

    # create one sighting to give us some annots to test against
    previous_sighting_uuids = asset_group_utils.create_complex_asset_group_uuids(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        filename='zebra2.jpg',
        detection_model='african_terrestrial',
        location_id=region1_id,
    )
    ags_guid = previous_sighting_uuids['asset_group_sighting']
    # wait for detection to finish
    test_utils.wait_for_progress(
        flask_app, [previous_sighting_uuids['progress_detection']]
    )
    # manually add annots to encounter
    asset_group_utils.assign_annot_to_encounter(flask_app_client, researcher_1, ags_guid)
    # commit it
    asset_group_utils.commit_asset_group_sighting(
        flask_app_client, researcher_1, ags_guid
    )

    uuids = asset_group_utils.create_complex_asset_group_uuids(
        flask_app_client,
        researcher_1,
        request,
        test_root,
        detection_model='african_terrestrial',
    )
    ags_guid = uuids['asset_group_sighting']
    # wait for detection to finish
    test_utils.wait_for_progress(flask_app, [uuids['progress_detection']])

    # manually add annots to encounter
    annot_guid, encounter_guid = asset_group_utils.assign_annot_to_encounter(
        flask_app_client, researcher_1, ags_guid
    )

    # Do a custom ID config
    patch_data = [
        {
            'op': 'replace',
            'path': '/idConfigs',
            'value': [
                {
                    'algorithms': ['hotspotter_nosv'],
                    'matching_set': {
                        'bool': {
                            'filter': [
                                {
                                    'bool': {
                                        'minimum_should_match': 1,
                                        'should': [{'term': {'locationId': region1_id}}],
                                    }
                                }
                            ]
                        }
                    },
                }
            ],
        }
    ]
    asset_group_utils.patch_asset_group_sighting_as_sighting(
        flask_app_client, researcher_1, ags_guid, patch_data
    )
    # commit it
    commit_response = asset_group_utils.commit_asset_group_sighting(
        flask_app_client, researcher_1, uuids['asset_group_sighting']
    ).json
    sighting_uuid = commit_response['guid']
    progress_id_guid = commit_response['progress_identification']['guid']
    # wait for id to complete
    test_utils.wait_for_progress(flask_app, [progress_id_guid])

    sighting_data = sighting_utils.read_sighting(
        flask_app_client, researcher_1, sighting_uuid
    ).json
    assert len(sighting_data['encounters']) == 1
    assert sighting_data['encounters'][0]['annotations'][0]['guid'] == annot_guid

    # TODO more validation of the outcome
