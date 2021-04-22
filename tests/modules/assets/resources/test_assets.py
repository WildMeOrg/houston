# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import hashlib
from tests import utils
import tests.modules.submissions.resources.utils as asset_group_utils


def test_get_asset_not_found(flask_app_client):
    response = flask_app_client.get('/api/v1/assets/wrong-uuid')
    assert response.status_code == 404


def test_find_asset(
    flask_app_client,
    admin_user,
    researcher_1,
    test_clone_asset_group_data,
):
    # Clone the known asset_group so that the asset data is in the database
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
        later_usage=True,
    )

    try:
        test_asset = '/api/v1/assets/%s' % test_clone_asset_group_data['asset_uuids'][0]
        test_src_asset = (
            '/api/v1/assets/src/%s' % test_clone_asset_group_data['asset_uuids'][0]
        )

        with flask_app_client.login(researcher_1, auth_scopes=('assets:read',)):
            response = flask_app_client.get(test_asset)
            src_response = flask_app_client.get(test_src_asset)
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert response.json['filename'] == 'zebra.jpg'
        assert response.json['src'] == test_src_asset
        assert src_response.status_code == 200
        assert src_response.content_type == 'image/jpeg'
        hexdigest = hashlib.md5(src_response.data).hexdigest()
        assert hexdigest in [
            '9c2e4476488534c05b7c557a0e663ccd',
            '0cd08301ba591bb98002667d75dc9e47',
        ]

        # Force the server to release the file handler
        src_response.close()
    finally:
        clone.cleanup()


def test_find_deleted_asset(
    flask_app_client,
    admin_user,
    researcher_1,
    db,
    test_clone_asset_group_data,
):
    # Clone the known asset_group so that the asset data is in the database
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
        later_usage=True,
    )

    try:
        # As for the test above but now remove the files so that Houston knows about the asset but does not have the files
        clone.remove_files()

        test_asset = '/api/v1/assets/%s' % test_clone_asset_group_data['asset_uuids'][0]
        test_src_asset = (
            '/api/v1/assets/src/%s' % test_clone_asset_group_data['asset_uuids'][0]
        )
        with flask_app_client.login(researcher_1, auth_scopes=('assets:read',)):
            response = flask_app_client.get(test_asset)
            src_response = flask_app_client.get(test_src_asset)

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert response.json['filename'] == 'zebra.jpg'
        assert response.json['src'] == test_src_asset
        assert src_response.status_code == 200
        assert src_response.content_type == 'image/jpeg'
        hexdigest = hashlib.md5(src_response.data).hexdigest()
        assert hexdigest in [
            '9c2e4476488534c05b7c557a0e663ccd',
            '0cd08301ba591bb98002667d75dc9e47',
        ]

        # Force the server to release the file handler
        src_response.close()
    finally:
        clone.cleanup()


def test_user_asset_permissions(
    flask_app_client,
    admin_user,
    researcher_1,
    readonly_user,
    db,
    test_clone_asset_group_data,
):
    # Clone the known asset_group so that the asset data is in the database
    clone = asset_group_utils.clone_asset_group(
        flask_app_client,
        admin_user,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
        later_usage=True,
    )

    try:
        test_asset = '/api/v1/assets/%s' % test_clone_asset_group_data['asset_uuids'][0]
        # Try reading it as a different user and check this fails
        with flask_app_client.login(readonly_user, auth_scopes=('assets:read',)):
            response = flask_app_client.get(test_asset)

        assert response.status_code == 403
    finally:
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
        admin_user,
        researcher_1,
        test_clone_asset_group_data['asset_group_uuid'],
        later_usage=True,
    )

    try:
        with flask_app_client.login(admin_user, auth_scopes=('assets:read',)):
            admin_response = flask_app_client.get('/api/v1/assets/')
        with flask_app_client.login(researcher_1, auth_scopes=('assets:read',)):
            researcher_response = flask_app_client.get('/api/v1/assets/')

        assert admin_response.status_code == 200
        assert admin_response.content_type == 'application/json'
        assert len(admin_response.json) == 2
        # both of these lists should be lexical order
        assert (
            admin_response.json[0]['guid']
            == test_clone_asset_group_data['asset_uuids'][0]
        )
        assert (
            admin_response.json[1]['guid']
            == test_clone_asset_group_data['asset_uuids'][1]
        )
        utils.validate_dict_response(researcher_response, 403, {'status', 'message'})
    finally:
        clone.cleanup()
