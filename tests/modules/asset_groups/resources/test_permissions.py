# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.assets.resources.utils as asset_utils
import tests.extensions.tus.utils as tus_utils
from tests import utils as test_utils
import uuid

from flask import current_app


def test_user_read_permissions(
    flask_app_client,
    admin_user,
    researcher_1,
    readonly_user,
    db,
    test_clone_asset_group_data,
):
    # Clone as the researcher user and then try to reread as both researcher and readonly user,
    # read by researcher user should succeed, read by readonly user should be blocked

    asset_group_utils.clone_asset_group(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    asset_utils.read_asset(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_uuids'][0],
    )
    asset_group_utils.read_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )
    asset_utils.read_asset(
        flask_app_client,
        readonly_user,
        test_clone_asset_group_data['asset_uuids'][0],
        403,
    )
    asset_group_utils.read_asset_group(
        flask_app_client,
        readonly_user,
        test_clone_asset_group_data['asset_group_uuid'],
        403,
    )
    # and as no user
    asset_group_utils.read_asset_group(
        flask_app_client, None, test_clone_asset_group_data['asset_group_uuid'], 401
    )


def test_create_patch_asset_group(
    flask_app_client, researcher_1, readonly_user, test_root, db
):
    # pylint: disable=invalid-name

    asset_group_guid = None
    transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)
    try:
        from app.modules.asset_groups.models import AssetGroup

        data = asset_group_utils.TestCreationData(transaction_id)
        data.add_filename(0, 0, test_filename)

        create_response = asset_group_utils.create_asset_group(
            flask_app_client, researcher_1, data.get()
        )
        assert create_response.json['description'] == data.get()['description']
        asset_group_guid = create_response.json['guid']
        temp_asset_group = AssetGroup.query.get(asset_group_guid)

        # reassign ownership
        patch_data = [
            test_utils.patch_add_op(
                'description', 'This is a test asset_group, kindly ignore'
            ),
        ]

        # Try to patch as non owner and validate it fails
        asset_group_utils.patch_asset_group(
            flask_app_client, readonly_user, asset_group_guid, patch_data, 403
        )

        # Should pass as owner
        patch_response = asset_group_utils.patch_asset_group(
            flask_app_client, researcher_1, asset_group_guid, patch_data
        )

        assert patch_response.json['description'] == patch_data[0]['value']
        assert patch_response.json['guid'] == asset_group_guid

        db.session.refresh(temp_asset_group)

        # Readonly user should not be able to delete
        asset_group_utils.delete_asset_group(
            flask_app_client, readonly_user, asset_group_guid, 403
        )

        # researcher should
        asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, asset_group_guid
        )
        current_app.git_backend.delete_remote_asset_group(temp_asset_group)

        # And if the asset_group is already gone, a re attempt at deletion should get the same response
        asset_group_utils.delete_asset_group(
            flask_app_client, researcher_1, asset_group_guid
        )

        # As should a delete of a random uuid
        asset_group_utils.delete_asset_group(flask_app_client, researcher_1, uuid.uuid4())

    finally:
        tus_utils.cleanup_tus_dir(transaction_id)
        current_app.git_backend.delete_remote_asset_group(temp_asset_group)
        # Restore original state
        temp_asset_group = AssetGroup.query.get(asset_group_guid)
        if temp_asset_group is not None:
            temp_asset_group.delete()
