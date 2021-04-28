# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid
import tests.modules.asset_groups.resources.utils as utils


def test_ensure_asset_group_by_uuid(
    flask_app_client, admin_user, researcher_1, db, test_asset_group_uuid
):
    utils.clone_asset_group(
        flask_app_client, admin_user, researcher_1, test_asset_group_uuid
    )


def test_ensure_empty_asset_group_by_uuid(
    flask_app_client, admin_user, researcher_1, db, test_empty_asset_group_uuid
):
    utils.clone_asset_group(
        flask_app_client, admin_user, researcher_1, test_empty_asset_group_uuid
    )


def test_ensure_clone_asset_group_by_uuid(
    flask_app_client, admin_user, researcher_1, db, test_clone_asset_group_data
):
    from app.modules.asset_groups.models import AssetGroupMajorType
    from app.modules.assets.models import Asset

    clone = utils.clone_asset_group(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    assert clone.asset_group.major_type == AssetGroupMajorType.test
    # assert clone.asset_group.commit == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    assert clone.asset_group.commit_mime_whitelist_guid == uuid.UUID(
        '4d46c55d-accf-29f1-abe7-a24839ec1b95'
    )

    # assert clone.asset_group.commit_houston_api_version == '0.1.0.xxxxxxxx'
    assert (
        clone.asset_group.description
        == 'This is a required PyTest submission (do not delete)'
    )

    # Checks that there are two valid Assets in the database
    assert len(clone.asset_group.assets) == 2
    temp_assets = sorted(clone.asset_group.assets)
    expected_guid_list = [
        uuid.UUID(test_clone_asset_group_data['asset_uuids'][0]),
        uuid.UUID(test_clone_asset_group_data['asset_uuids'][1]),
    ]

    for asset, expected_guid in zip(temp_assets, expected_guid_list):
        db_asset = Asset.query.get(asset.guid)
        assert asset == db_asset
        assert asset.guid == expected_guid
