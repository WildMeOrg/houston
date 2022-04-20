# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import hashlib

import tests.extensions.tus.utils as tus_utils
import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.assets.resources.utils as asset_utils
import pytest

from tests.utils import module_unavailable


# md5sum values of the initial and derived files
initial_md5sum_values = [
    '6b383b9feb55b14ec7f8d469402aff01',
    '97eac24832b42b2021b84bb367bde571',
]
derived_md5sum_values = [
    '9c2e4476488534c05b7c557a0e663ccd',
    '0cd08301ba591bb98002667d75dc9e47',
]


def test_get_asset_not_found(flask_app_client, researcher_1):
    import uuid

    asset_utils.read_asset(flask_app_client, None, str(uuid.uuid4()), 404)
    asset_utils.read_asset(flask_app_client, researcher_1, str(uuid.uuid4()), 404)
    response = flask_app_client.get('/api/v1/assets/invalid-uuid')
    assert response.status_code == 404
    response.close()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_find_asset(
    flask_app_client,
    researcher_1,
    request,
    test_root,
):
    uuids = asset_group_utils.create_simple_asset_group_uuids(
        flask_app_client, researcher_1, request, test_root
    )
    asset_guid = uuids['assets'][0]

    asset_response = asset_utils.read_asset(flask_app_client, researcher_1, asset_guid)
    assert asset_response.json['filename'] == 'zebra.jpg'
    assert asset_response.json['src'] == f'/api/v1/assets/src/{asset_guid}'

    src_response = None
    try:
        src_response = asset_utils.read_src_asset(
            flask_app_client, researcher_1, asset_guid
        )
        # Derived files are always jpegs
        assert src_response.content_type == 'image/jpeg'
    finally:
        # Force the server to release the file handler
        if src_response is not None:
            src_response.close()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_access_asset_src_by_different_roles(
    flask_app_client,
    admin_user,
    staff_user,
    request,
    test_root,
):
    """Test that an anonymous sighting upload's assets can be viewed by anyone
    See also, https://wildme.atlassian.net/browse/DEX-895

    """
    tus_transaction_id, test_filename = tus_utils.prep_tus_dir(test_root)

    asset_group_uuid = None
    try:
        # Create an "anonymous sighting"
        data = asset_group_utils.AssetGroupCreationData(tus_transaction_id, test_filename)
        user = None  # anonymous
        resp = asset_group_utils.create_asset_group(flask_app_client, user, data.get())

        asset_group_uuid = resp.json['guid']
        asset_guid = resp.json['assets'][0]['guid']

        # Access the asset src as the admin user
        asset_utils.read_src_asset(flask_app_client, admin_user, asset_guid)

        # Access the asset src as the staff user
        asset_utils.read_src_asset(flask_app_client, staff_user, asset_guid)

        # Access the asset src as an anonymous user
        asset_utils.read_src_asset(
            flask_app_client, None, asset_guid, expected_status_code=401
        )
    finally:
        if asset_group_uuid:
            asset_group_utils.delete_asset_group(
                flask_app_client, staff_user, asset_group_uuid
            )
        tus_utils.cleanup_tus_dir(tus_transaction_id)


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_find_deleted_asset(
    flask_app_client,
    researcher_1,
    db,
    test_clone_asset_group_data,
):
    # Clone the known asset_group so that the asset data is in the database
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    try:
        # remove the files so that Houston knows about the asset but does not have the files
        clone.remove_files()

        asset_guid = test_clone_asset_group_data['asset_uuids'][0]
        asset_response = asset_utils.read_asset(
            flask_app_client, researcher_1, asset_guid
        )
        src_response = asset_utils.read_src_asset(
            flask_app_client, researcher_1, asset_guid
        )

        assert asset_response.json['filename'] == 'zebra.jpg'
        assert asset_response.json['src'] == f'/api/v1/assets/src/{asset_guid}'
        assert src_response.content_type == 'image/jpeg'
        assert hashlib.md5(src_response.data).hexdigest() in derived_md5sum_values

        # Force the server to release the file handler
        src_response.close()
    finally:
        # Force the server to release the file handler
        src_response.close()
        clone.cleanup()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_find_raw_asset(
    flask_app_client,
    admin_user,
    researcher_1,
    internal_user,
    db,
    request,
    test_root,
):
    uuids = asset_group_utils.create_simple_asset_group_uuids(
        flask_app_client, researcher_1, request, test_root
    )
    asset_guid = uuids['assets'][0]

    # Only internal, not even uploader can read the raw src for the file
    asset_utils.read_raw_src_asset(flask_app_client, researcher_1, asset_guid, 403)
    asset_utils.read_raw_src_asset(flask_app_client, admin_user, asset_guid, 403)

    # Even internal is not allowed to access it if it's not in the detecting stage
    asset_utils.read_raw_src_asset(flask_app_client, internal_user, asset_guid, 403)
    from app.modules.asset_groups.models import (
        AssetGroupSightingStage,
        AssetGroupSighting,
    )

    new_sighting = AssetGroupSighting.query.get(uuids['asset_group_sighting'])

    # now force it back to 'detection' stage to permit testing
    new_sighting.stage = AssetGroupSightingStage.detection

    raw_src_response = None
    try:
        raw_src_response = asset_utils.read_raw_src_asset(
            flask_app_client, internal_user, asset_guid
        )

        assert raw_src_response.content_type == 'image/jpeg'
        assert hashlib.md5(raw_src_response.data).hexdigest() in initial_md5sum_values

        # Force the server to release the file handler
        raw_src_response.close()

    finally:
        # Force the server to release the file handler
        if raw_src_response:
            raw_src_response.close()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_user_asset_permissions(
    flask_app_client,
    researcher_1,
    readonly_user,
    db,
    request,
    test_root,
):
    uuids = asset_group_utils.create_simple_asset_group_uuids(
        flask_app_client, researcher_1, request, test_root
    )
    asset_guid = uuids['assets'][0]

    # Try reading it as a different user and check this fails
    asset_utils.read_asset(flask_app_client, readonly_user, asset_guid, 403)


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_read_all_assets(
    flask_app_client,
    admin_user,
    researcher_1,
    request,
    test_root,
):
    uuids = asset_group_utils.create_large_asset_group_uuids(
        flask_app_client, researcher_1, request, test_root
    )

    admin_response = asset_utils.read_all_assets(flask_app_client, admin_user)
    asset_utils.read_all_assets(flask_app_client, researcher_1, 403)

    # both of these lists should be lexical order
    asset_guids = [entry['guid'] for entry in admin_response.json]
    assert asset_guids == uuids['assets']


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_image_rotate(flask_app_client, researcher_1, request, test_root):
    uuids = asset_group_utils.create_simple_asset_group_uuids(
        flask_app_client, researcher_1, request, test_root
    )
    asset_guid = uuids['assets'][0]

    patch_data = [
        {
            'op': 'replace',
            'path': '/image',
            'value': {'rotate': {'angle': -90}},
        },
    ]
    error_msg = '"rotate.angle": Value must be greater than 0.'
    asset_utils.patch_asset(
        flask_app_client, asset_guid, researcher_1, patch_data, 422, error_msg
    )

    patch_data = [
        {
            'op': 'replace',
            'path': '/image',
            'value': {'rotate': {'angle': 90}},
        },
    ]
    response = asset_utils.patch_asset(
        flask_app_client, asset_guid, researcher_1, patch_data
    )

    assert response.json['filename'] == uuids['filename']
    assert response.json['dimensions'] == {'width': 664, 'height': 1000}
