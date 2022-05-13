# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.assets.resources.utils as asset_utils
from tests import utils as test_utils
import pytest

from tests.utils import module_unavailable


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_user_read_permissions(
    flask_app_client, researcher_1, readonly_user, db, request, test_root
):
    # Create as the researcher user and then try to reread as both researcher and readonly user,
    # read by researcher user should succeed, read by readonly user should be blocked
    uuids = asset_group_utils.create_simple_asset_group_uuids(
        flask_app_client, researcher_1, request, test_root
    )
    asset_guid = uuids['assets'][0]
    asset_group_guid = uuids['asset_group']

    asset_utils.read_asset(flask_app_client, researcher_1, asset_guid)
    asset_group_utils.read_asset_group(flask_app_client, researcher_1, asset_group_guid)
    asset_utils.read_asset(flask_app_client, readonly_user, asset_guid, 403)
    asset_group_utils.read_asset_group(
        flask_app_client, readonly_user, asset_group_guid, 403
    )
    # and as no user
    asset_group_utils.read_asset_group(flask_app_client, None, asset_group_guid, 403)


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_create_patch_asset_group(
    flask_app_client, researcher_1, readonly_user, test_root, db, request
):
    # pylint: disable=invalid-name
    uuids = asset_group_utils.create_simple_asset_group_uuids(
        flask_app_client, researcher_1, request, test_root
    )
    asset_group_guid = uuids['asset_group']
    from app.modules.asset_groups.models import AssetGroup

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
    asset_group_utils.delete_asset_group(flask_app_client, researcher_1, asset_group_guid)
    # temp_asset_group should be already deleted on gitlab
    assert not AssetGroup.is_on_remote(str(temp_asset_group.guid))

    # And if the asset_group is already gone, a re attempt at deletion should get the same response
    asset_group_utils.delete_asset_group(flask_app_client, researcher_1, asset_group_guid)

    # As should a delete of a random uuid
    asset_group_utils.delete_asset_group(flask_app_client, researcher_1, uuid.uuid4())
