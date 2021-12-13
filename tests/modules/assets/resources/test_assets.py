# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import hashlib
import json

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.assets.resources.utils as asset_utils
import tests.utils as test_utils
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
    test_clone_asset_group_data,
):
    # Clone the known asset_group so that the asset data is in the database
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    try:
        asset_guid = test_clone_asset_group_data['asset_uuids'][3]
        asset_response = asset_utils.read_asset(
            flask_app_client, researcher_1, asset_guid
        )
        assert asset_response.json['filename'] == 'coelacanth.png'
        assert asset_response.json['src'] == f'/api/v1/assets/src/{asset_guid}'

        src_response = asset_utils.read_src_asset(
            flask_app_client, researcher_1, asset_guid
        )
        # Derived files are always jpegs
        assert src_response.content_type == 'image/jpeg'
    finally:
        # Force the server to release the file handler
        src_response.close()
        clone.cleanup()


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
        # As for the test above but now remove the files so that Houston knows about the asset but does not have the files
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
    test_clone_asset_group_data,
):
    # Clone the known asset_group so that the asset data is in the database
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )
    raw_src_response = None
    try:
        asset_guid = test_clone_asset_group_data['asset_uuids'][0]

        # Only internal, not even uploader can read the raw src for the file
        asset_utils.read_raw_src_asset(flask_app_client, researcher_1, asset_guid, 403)
        asset_utils.read_raw_src_asset(flask_app_client, admin_user, asset_guid, 403)

        # Even internal is not allowed to access it if it's not in the detecting stage
        asset_utils.read_raw_src_asset(flask_app_client, internal_user, asset_guid, 403)
        from app.modules.asset_groups.models import (
            AssetGroupSightingStage,
            AssetGroupSighting,
        )

        new_sighting = AssetGroupSighting(
            asset_group=clone.asset_group,
            sighting_config=test_utils.dummy_sighting_info(),
            detection_configs=test_utils.dummy_detection_info(),
        )

        # now force it back to 'detection' stage to permit testing
        new_sighting.stage = AssetGroupSightingStage.detection

        raw_src_response = asset_utils.read_raw_src_asset(
            flask_app_client, internal_user, asset_guid
        )

        assert raw_src_response.content_type == 'image/jpeg'
        assert hashlib.md5(raw_src_response.data).hexdigest() in initial_md5sum_values

        # Force the server to release the file handler
        raw_src_response.close()

        raw_src_response = asset_utils.read_raw_src_asset(
            flask_app_client, internal_user, test_clone_asset_group_data['asset_uuids'][3]
        )

        assert raw_src_response.content_type == 'image/png'
    finally:
        # Force the server to release the file handler
        if raw_src_response:
            raw_src_response.close()
        clone.cleanup()
        new_sighting.delete()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_user_asset_permissions(
    flask_app_client,
    researcher_1,
    readonly_user,
    db,
    test_clone_asset_group_data,
):
    # Clone the known asset_group so that the asset data is in the database
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    # Try reading it as a different user and check this fails
    asset_guid = test_clone_asset_group_data['asset_uuids'][0]
    asset_utils.read_asset(flask_app_client, readonly_user, asset_guid, 403)

    clone.cleanup()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_read_all_assets(
    flask_app_client,
    admin_user,
    researcher_1,
    test_clone_asset_group_data,
):
    # Clone the known asset_group so that the asset data is in the database
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )

    admin_response = asset_utils.read_all_assets(flask_app_client, admin_user)
    asset_utils.read_all_assets(flask_app_client, researcher_1, 403)

    assert len(admin_response.json) == 4
    # both of these lists should be lexical order
    assert admin_response.json[0]['guid'] == test_clone_asset_group_data['asset_uuids'][0]
    assert admin_response.json[1]['guid'] == test_clone_asset_group_data['asset_uuids'][1]

    clone.cleanup()


@pytest.mark.skipif(
    module_unavailable('asset_groups'), reason='AssetGroups module disabled'
)
def test_patch_image_rotate(
    flask_app_client, researcher_1, test_clone_asset_group_data, request
):
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
    )
    request.addfinalizer(clone.cleanup)
    asset = clone.asset_group.assets[0]

    def asset_cleanup():
        original = asset.get_original_path()
        original.rename(asset.get_symlink().resolve())
        asset.reset_derived_images()

    with flask_app_client.login(researcher_1, auth_scopes=('assets:write',)):
        response = flask_app_client.patch(
            f'/api/v1/assets/{asset.guid}',
            content_type='application/json',
            data=json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/image',
                        'value': {'rotate': {'angle': -90}},
                    },
                ],
            ),
        )
        assert response.status_code == 422
        assert response.json['message'] == '"rotate.angle": Value must be greater than 0.'

        response = flask_app_client.patch(
            f'/api/v1/assets/{asset.guid}',
            content_type='application/json',
            data=json.dumps(
                [
                    {
                        'op': 'replace',
                        'path': '/image',
                        'value': {'rotate': {'angle': 90}},
                    },
                ],
            ),
        )
        request.addfinalizer(asset_cleanup)
        assert response.status_code == 200
        assert response.json['filename'] == 'zebra.jpg'
        assert response.json['dimensions'] == {'width': 664, 'height': 1000}
