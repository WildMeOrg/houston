# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.sightings.resources.utils as sighting_utils
import tests.extensions.tus.utils as tus_utils


# Test a bunch of failure scenarios
def test_commit_asset_group(flask_app_client, researcher_1, regular_user, test_root, db):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData
    from app.modules.sightings.models import Sighting, SightingStage

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
        asset_group_sighting_guid = response.json['asset_group_sightings'][0]['guid']
        asset_uuid = response.json['assets'][0]['guid']
        asset_group_utils.patch_in_dummy_annotation(
            flask_app_client, db, researcher_1, asset_group_sighting_guid, asset_uuid
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
        assert sighting.stage == SightingStage.un_reviewed
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


def test_commit_owner_asset_group(
    flask_app_client, researcher_1, regular_user, staff_user, test_root, db
):
    # pylint: disable=invalid-name
    from app.modules.sightings.models import Sighting, SightingStage

    transaction_id, test_filename = asset_group_utils.create_bulk_tus_transaction(
        test_root
    )
    asset_group_uuid = None
    sighting_uuid = None
    try:
        data = asset_group_utils.get_bulk_creation_data(transaction_id, test_filename)
        data.set_encounter_field(0, 0, 'ownerEmail', regular_user.email)
        resp = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        asset_group_uuid = resp.json['guid']
        asset_group_sighting_guid = resp.json['asset_group_sightings'][0]['guid']
        # commit it
        response = asset_group_utils.commit_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_guid
        )
        sighting_uuid = response.json['guid']
        sighting = Sighting.query.get(sighting_uuid)
        encounters = sighting.get_encounters()
        assert len(encounters) == 2
        assert sighting.stage == SightingStage.un_reviewed
        # It seems encounters may not be returned in order so we can't assert
        # encounters[0].owner == regular_user
        assert sorted([e.owner.email for e in encounters]) == [
            researcher_1.email,
            regular_user.email,
        ]

    finally:
        # Restore original state
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, researcher_1, asset_group_uuid
            )
        if sighting_uuid:
            sighting_utils.delete_sighting(flask_app_client, staff_user, sighting_uuid)
        tus_utils.cleanup_tus_dir(transaction_id)


# Create an asset group with an annotation and an ia_config and expect it to start IA
def test_commit_asset_group_ia(
    flask_app_client, researcher_1, regular_user, test_root, db
):
    # pylint: disable=invalid-name
    from tests.modules.asset_groups.resources.utils import TestCreationData
    from app.modules.sightings.models import Sighting, SightingStage

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
        asset_group_sighting_guid = response.json['asset_group_sightings'][0]['guid']
        asset_uuid = response.json['assets'][0]['guid']
        asset_group_utils.patch_in_dummy_annotation(
            flask_app_client, db, researcher_1, asset_group_sighting_guid, asset_uuid
        )

        ia_config = {
            'algorithms': [
                'noddy',
            ],
        }
        asset_group_utils.patch_in_ia_config(
            flask_app_client, researcher_1, asset_group_sighting_guid, ia_config, 400
        )
        ia_config['matchingSetDataOwners'] = 'someone_elses'
        asset_group_utils.patch_in_ia_config(
            flask_app_client, researcher_1, asset_group_sighting_guid, ia_config, 400
        )
        ia_config['matchingSetDataOwners'] = 'mine'
        asset_group_utils.patch_in_ia_config(
            flask_app_client, researcher_1, asset_group_sighting_guid, ia_config, 200
        )

        response = asset_group_utils.commit_asset_group_sighting(
            flask_app_client, researcher_1, asset_group_sighting_guid
        )
        sighting_uuid = response.json['guid']
        sighting = Sighting.query.get(sighting_uuid)
        assert sighting.stage == SightingStage.un_reviewed
    finally:
        # Restore original state
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, regular_user, asset_group_uuid
            )
        if sighting_uuid:
            sighting_utils.delete_sighting(flask_app_client, regular_user, sighting_uuid)
        tus_utils.cleanup_tus_dir(transaction_id)
