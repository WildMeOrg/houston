# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.users.resources.utils as user_utils
import tests.modules.audit_logs.resources.utils as audit_utils


def test_audit_asset_group_creation(
    flask_app_client, researcher_1, contributor_1, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData

    asset_group_uuid = None
    sighting_uuid = None
    try:
        data = TestCreationData(None)
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
