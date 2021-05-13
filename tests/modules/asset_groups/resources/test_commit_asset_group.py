# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.extensions.tus.utils as tus_utils
from flask import current_app


# Test a bunch of failure scenarios
def test_create_asset_group(flask_app_client, researcher_1, regular_user, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    temp_submission = None

    try:
        from app.modules.asset_groups.models import AssetGroup

        data = TestCreationData(transaction_id)
        data.add_filename(0, 0, test_filename)
        response = asset_group_utils.create_asset_group(
            flask_app_client, regular_user, data.get()
        )
        asset_group_guid = response.json['guid']
        asset_group_sighting_guid = response.json['sightings'][0]['guid']
        temp_submission = AssetGroup.query.get(asset_group_guid)

        response = asset_group_utils.commit_asset_group_sighting(
            flask_app_client, regular_user, asset_group_guid, asset_group_sighting_guid
        )

    finally:
        current_app.git_backend.delete_remote_asset_group(temp_submission)
        # Restore original state
        if temp_submission is not None:
            temp_submission.delete()
