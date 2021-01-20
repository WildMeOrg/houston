# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import hashlib
from tests.utils import clone_submission


def test_find_asset(
    flask_app_client,
    regular_user,
    db,
    test_clone_submission_data,
):
    # Clone the known submission so that the asset data is in the database
    clone = clone_submission(
        flask_app_client,
        regular_user,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )

    try:
        test_asset = '/api/v1/assets/%s' % test_clone_submission_data['asset_uuids'][0]
        test_src_asset = (
            '/api/v1/assets/src/%s' % test_clone_submission_data['asset_uuids'][0]
        )
        with flask_app_client.login(regular_user, auth_scopes=('assets:read',)):
            response = flask_app_client.get(test_asset)
            src_response = flask_app_client.get(test_src_asset)

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert response.json['filename'] == 'fluke.jpg'
        assert response.json['src'] == test_src_asset
        assert src_response.status_code == 200
        assert src_response.content_type == 'image/jpeg'
        assert (
            hashlib.md5(src_response.data).hexdigest()
            == '0b546f813ec9631ce5c9b1dd579c623b'
        )

        # Force the server to release the file handler
        src_response.close()

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()


def test_find_deleted_asset(
    flask_app_client,
    regular_user,
    db,
    test_clone_submission_data,
):
    # Clone the known submission so that the asset data is in the database
    clone = clone_submission(
        flask_app_client,
        regular_user,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )

    try:
        # As for the test above but now remove the files so that Houston knows about the asset but does not have the files
        clone.remove_files()

        test_asset = '/api/v1/assets/%s' % test_clone_submission_data['asset_uuids'][0]
        test_src_asset = (
            '/api/v1/assets/src/%s' % test_clone_submission_data['asset_uuids'][0]
        )
        with flask_app_client.login(regular_user, auth_scopes=('assets:read',)):
            response = flask_app_client.get(test_asset)
            src_response = flask_app_client.get(test_src_asset)

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert response.json['filename'] == 'fluke.jpg'
        assert response.json['src'] == test_src_asset
        assert src_response.status_code == 200
        assert src_response.content_type == 'image/jpeg'
        assert (
            hashlib.md5(src_response.data).hexdigest()
            == '0b546f813ec9631ce5c9b1dd579c623b'
        )

        # Force the server to release the file handler
        src_response.close()

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()


def test_user_asset_permissions(
    flask_app_client,
    regular_user,
    readonly_user,
    db,
    test_clone_submission_data,
):
    # Clone the known submission so that the asset data is in the database
    clone = clone_submission(
        flask_app_client,
        regular_user,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )

    try:
        test_asset = '/api/v1/assets/%s' % test_clone_submission_data['asset_uuids'][0]
        # Try reading it as a different user and check this fails
        with flask_app_client.login(readonly_user, auth_scopes=('assets:read',)):
            response = flask_app_client.get(test_asset)

        assert response.status_code == 403

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()


def test_read_all_assets(
    flask_app_client,
    regular_user,
    admin_user,
    db,
    test_clone_submission_data,
):
    # Clone the known submission so that the asset data is in the database
    clone = clone_submission(
        flask_app_client,
        regular_user,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )

    try:
        with flask_app_client.login(admin_user, auth_scopes=('assets:read',)):
            admin_response = flask_app_client.get('/api/v1/assets/')
        with flask_app_client.login(regular_user, auth_scopes=('assets:read',)):
            regular_response = flask_app_client.get('/api/v1/assets/')

        assert admin_response.status_code == 200
        assert admin_response.content_type == 'application/json'
        assert len(admin_response.json) == 2
        # @todo, is the order received deterministic
        assert (
            admin_response.json[0]['guid'] == test_clone_submission_data['asset_uuids'][1]
        )
        assert (
            admin_response.json[1]['guid'] == test_clone_submission_data['asset_uuids'][0]
        )
        assert regular_response.status_code == 403

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()
