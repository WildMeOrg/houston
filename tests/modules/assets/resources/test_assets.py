# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import hashlib

import tests.modules.asset_groups.resources.utils as asset_group_utils
import tests.modules.assets.resources.utils as asset_utils

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

    asset_utils.read_asset(flask_app_client, None, str(uuid.uuid4()), 401)
    asset_utils.read_asset(flask_app_client, researcher_1, str(uuid.uuid4()), 404)
    # TODO, this is what the test did previously, does this make sense?
    response = flask_app_client.get('/api/v1/assets/wrong-uuid')
    assert response.status_code == 404


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
        asset_guid = test_clone_asset_group_data['asset_uuids'][0]
        asset_response = asset_utils.read_asset(
            flask_app_client, researcher_1, asset_guid
        )
        src_response = asset_utils.read_src_asset(
            flask_app_client, researcher_1, asset_guid
        )

        assert asset_response.json['filename'] == 'zebra.jpg'
        assert asset_response.json['src'] == f'/api/v1/assets/src/{asset_guid}'
        assert hashlib.md5(src_response.data).hexdigest() in derived_md5sum_values

        # Force the server to release the file handler
        src_response.close()
    finally:
        # Force the server to release the file handler
        src_response.close()
        clone.cleanup()


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
        assert hashlib.md5(src_response.data).hexdigest() in derived_md5sum_values

        # Force the server to release the file handler
        src_response.close()
    finally:
        # Force the server to release the file handler
        src_response.close()
        clone.cleanup()


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
            stage=AssetGroupSightingStage.detection,
            asset_group_guid=clone.asset_group.guid,
        )
        with db.session.begin():
            db.session.add(new_sighting)
            clone.asset_group.asset_group_sightings.append(new_sighting)

        raw_src_response = asset_utils.read_raw_src_asset(
            flask_app_client, internal_user, asset_guid
        )

        assert hashlib.md5(raw_src_response.data).hexdigest() in initial_md5sum_values

        # Force the server to release the file handler
        raw_src_response.close()
    finally:
        # Force the server to release the file handler
        if raw_src_response:
            raw_src_response.close()
        clone.cleanup()


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

    assert len(admin_response.json) == 2
    # both of these lists should be lexical order
    assert admin_response.json[0]['guid'] == test_clone_asset_group_data['asset_uuids'][0]
    assert admin_response.json[1]['guid'] == test_clone_asset_group_data['asset_uuids'][1]

    clone.cleanup()
