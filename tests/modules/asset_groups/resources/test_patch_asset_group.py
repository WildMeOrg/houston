# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.extensions.tus.utils as tus_utils


# Test a bunch of failure scenarios
def test_patch_asset_group(flask_app_client, researcher_1, regular_user, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData
    from tests import utils

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    try:
        data = TestCreationData(transaction_id)
        data.add_filename(0, test_filename)
        response = asset_group_utils.create_asset_group(
            flask_app_client, regular_user, data.get()
        )
        asset_group_uuid = response.json['guid']
        asset_group_sighting_guid = response.json['asset_group_sightings'][0]['guid']

        # Regular user can create it but not read it??????
        asset_group_utils.read_asset_group_sighting(
            flask_app_client, regular_user, asset_group_sighting_guid, 403
        )

        # Researcher should be able to
        group_sighting = asset_group_utils.read_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_guid
        )

        assert 'config' in group_sighting.json
        assert 'assetReferences' in group_sighting.json['config']
        import copy

        new_absent_file = copy.deepcopy(group_sighting.json['config']['assetReferences'])
        new_absent_file.append('absent_file.jpg')
        patch_data = [utils.patch_replace_op('assetReferences', new_absent_file)]
        asset_group_utils.patch_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_guid, patch_data, 400
        )

        # Valid patch, adding a new encounter with an existing file
        new_encounters = copy.deepcopy(group_sighting.json['config']['encounters'])
        new_encounters.append({})
        patch_data = [utils.patch_replace_op('encounters', new_encounters)]

        # Should not work as contributor
        asset_group_utils.patch_asset_group_sighting(
            flask_app_client, regular_user, asset_group_sighting_guid, patch_data, 403
        )

        # should work as researcher
        asset_group_utils.patch_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_guid, patch_data
        )

        # chosen for reasons of incongruity as the naked mole rat is virtually blind
        # so has no 'sight'
        add_name_patch = [utils.patch_add_op('name', 'Naked Mole Rat')]
        asset_group_utils.patch_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_guid, add_name_patch
        )

    finally:
        # Restore original state
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, regular_user, asset_group_uuid
            )

        tus_utils.cleanup_tus_dir(transaction_id)
