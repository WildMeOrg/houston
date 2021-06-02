# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.extensions.tus.utils as tus_utils


# Test a bunch of failure scenarios
def test_commit_asset_group(flask_app_client, researcher_1, regular_user, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = TestCreationData(transaction_id)
        data.add_filename(0, test_filename)
        response = asset_group_utils.create_asset_group(
            flask_app_client, regular_user, data.get()
        )
        asset_group_uuid = response.json['guid']
        asset_group_sighting_guid = response.json['sightings'][0]['guid']

        # Should not be able to commit as contributor
        asset_group_utils.commit_asset_group_sighting(
            flask_app_client, regular_user, asset_group_sighting_guid, 403
        )
        # researcher should though
        response = asset_group_utils.commit_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_guid
        )
        from app.modules.sightings.models import Sighting

        sighting = Sighting.query.get(response.json['guid'])
        assert len(sighting.get_encounters()) == 1
        # TODO restore once sightings have assets again
        # assert len(sighting.get_assets()) == 1
        assert sighting.get_owner() == regular_user

    finally:
        # Restore original state
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, regular_user, asset_group_uuid
            )

        tus_utils.cleanup_tus_dir(transaction_id)
