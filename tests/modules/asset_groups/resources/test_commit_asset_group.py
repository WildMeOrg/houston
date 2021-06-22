# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.extensions.tus.utils as tus_utils
from tests import utils as test_utils
import uuid


# Test a bunch of failure scenarios
def test_commit_asset_group(flask_app_client, researcher_1, regular_user, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData
    from app.modules.sightings.models import Sighting
    from app.modules.assets.models import Asset
    from app.modules.annotations.models import Annotation

    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    asset_group_uuid = None
    sighting_uuid = None
    try:
        data = TestCreationData(transaction_id)
        data.add_filename(0, test_filename)
        response = asset_group_utils.create_asset_group(
            flask_app_client, regular_user, data.get()
        )
        asset_group_uuid = response.json['guid']
        asset_group_sighting_guid = response.json['sightings'][0]['guid']
        asset_uuid = response.json['assets'][0]['guid']
        asset = Asset.find(asset_uuid)
        assert asset

        # Create a dummy annotation for this Sighting
        new_annot = Annotation(
            guid=uuid.uuid4(),
            asset=asset,
            ia_class='none',
            bounds={'rect': [45, 5, 78, 3], 'theta': 4.8},
        )
        with db.session.begin(subtransactions=True):
            db.session.add(new_annot)

        # Patch it in
        group_sighting = asset_group_utils.read_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_guid
        )

        import copy

        new_annot_data = copy.deepcopy(group_sighting.json['config'])
        new_annot_data['encounters'][0]['annotations'] = [str(new_annot.guid)]
        patch_data = [test_utils.patch_replace_op('config', new_annot_data)]
        asset_group_utils.patch_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_guid, patch_data
        )

        # Should not be able to commit as contributor
        asset_group_utils.commit_asset_group_sighting(
            flask_app_client, regular_user, asset_group_sighting_guid, 403
        )
        # researcher should though
        response = asset_group_utils.commit_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_guid
        )

        sighting_uuid = response.json['guid']
        sighting = Sighting.query.get(sighting_uuid)
        assert len(sighting.get_encounters()) == 1
        assert len(sighting.get_assets()) == 1
        assert sighting.get_owner() == regular_user

    finally:
        # Restore original state
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, regular_user, asset_group_uuid
            )
        if sighting_uuid:
            sighting_utils.delete_sighting(flask_app_client, regular_user, sighting_uuid)
        tus_utils.cleanup_tus_dir(transaction_id)
