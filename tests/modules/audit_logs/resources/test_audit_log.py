# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.users.resources.utils as user_utils
import tests.modules.audit_logs.resources.utils as audit_utils
import tests.modules.sightings.resources.utils as sighting_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_audit_asset_group_creation(
    flask_app_client, researcher_1, contributor_1, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import AssetGroupCreationData

    asset_group_uuid = None
    sighting_uuid = None
    try:
        data = AssetGroupCreationData(None)
        data.remove_field('transactionId')

        # Create an asset group without any assets as we don't need them, we want it to commit straight away and
        # create the Sighting/Encounter
        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = resp.json['guid']

        # Make sure that the user has a single unprocessed sighting
        user_resp = user_utils.read_user(flask_app_client, researcher_1, 'me')
        assert 'unprocessed_sightings' in user_resp.json
        assert len(user_resp.json['unprocessed_sightings']) == 1
        sighting_uuid = user_resp.json['unprocessed_sightings'][0]
        from app.modules.sightings.models import Sighting

        sighting = Sighting.query.get(sighting_uuid)
        audit_utils.read_all_audit_logs(flask_app_client, contributor_1, 403)

        expected_sighting = {'module_name': 'Sighting', 'item_guid': sighting_uuid}
        expected_encounter = {
            'module_name': 'Encounter',
            'item_guid': str(sighting.encounters[0].guid),
        }

        sighting_audit_items = audit_utils.read_all_audit_logs(
            flask_app_client, researcher_1, module_name='Sighting'
        )
        assert expected_sighting in sighting_audit_items.json
        assert expected_encounter not in sighting_audit_items.json
        encounter_audit_items = audit_utils.read_all_audit_logs(
            flask_app_client, researcher_1, module_name='Encounter'
        )
        assert expected_sighting not in encounter_audit_items.json
        assert expected_encounter in encounter_audit_items.json

        audit_utils.read_audit_log(flask_app_client, contributor_1, sighting_uuid, 403)
        sighting_audit = audit_utils.read_audit_log(
            flask_app_client, researcher_1, sighting_uuid
        )
        assert len(sighting_audit.json) == 1
        log_entry = sighting_audit.json[0]
        assert log_entry['user_email'] == researcher_1.email
        assert log_entry['module_name'] == 'Sighting'
        assert log_entry['item_guid'] == sighting_uuid

    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        if sighting_uuid:
            import tests.modules.sightings.resources.utils as sighting_utils

            sighting_utils.delete_sighting(flask_app_client, researcher_1, sighting_uuid)


# Basically a duplication of the ia pipeline up to Sighting creation and making sure that the required audit
# logs are present
@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_most_ia_pipeline_audit_log(
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

    asset_group_uuid = None

    # Use a real detection model to trigger a request sent to Sage
    data = asset_group_utils.get_bulk_creation_data(
        test_root, request, 'african_terrestrial'
    )

    # and the sim_sage util to catch it
    resp = asset_group_utils.create_asset_group_sim_sage_init_resp(
        flask_app, flask_app_client, researcher_1, data.get()
    )
    asset_group_uuid = resp.json['guid']
    request.addfinalizer(
        lambda: asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, asset_group_uuid
        )
    )
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
    request.addfinalizer(
        lambda: sighting_utils.delete_sighting(
            flask_app_client, staff_user, sighting_uuid
        )
    )
    sighting = Sighting.query.get(sighting_uuid)
    encounters = sighting.get_encounters()
    assert len(encounters) == 2

    # Everything up to here was setting the stage, now to start the test of the contents of the audit log.
    expected_sighting = {'module_name': 'Sighting', 'item_guid': sighting_uuid}
    expected_encounter = {
        'module_name': 'Encounter',
        'item_guid': str(encounters[0].guid),
    }

    sighting_audit_items = audit_utils.read_all_audit_logs(
        flask_app_client, researcher_1, module_name='Sighting'
    )
    encounter_audit_items = audit_utils.read_all_audit_logs(
        flask_app_client, researcher_1, module_name='Encounter'
    )

    assert expected_sighting in sighting_audit_items.json
    assert expected_encounter in encounter_audit_items.json


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_audit_log_faults(
    flask_app_client, researcher_1, readonly_user, admin_user, test_root, db
):
    # Reuse a different test that generates a truckload of faults
    from tests.modules.asset_groups.resources.test_create_asset_group import (
        test_create_asset_group,
    )

    test_create_asset_group(flask_app_client, researcher_1, readonly_user, test_root, db)
    audit_utils.read_all_faults(flask_app_client, researcher_1, 403)
    faults = audit_utils.read_all_faults(flask_app_client, admin_user)

    # arbitrary choice but it must be at least this many from the test
    expected_faults = 9
    assert len(faults.json) >= expected_faults
    for fault_no in range(0, expected_faults - 1):
        assert faults.json[fault_no]['audit_type'] == 'Front End Fault'
