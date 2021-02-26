# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import hashlib
from tests import utils


def test_find_asset(
    flask_app_client,
    regular_user,
    test_clone_submission_data,
):
    # Clone the known submission so that the asset data is in the database
    clone = utils.clone_submission(
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
        assert response.json['filename'] == 'zebra.jpg'
        assert response.json['src'] == test_src_asset
        assert src_response.status_code == 200
        assert src_response.content_type == 'image/jpeg'
        assert (
            hashlib.md5(src_response.data).hexdigest()
            == '9c2e4476488534c05b7c557a0e663ccd'
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
    clone = utils.clone_submission(
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
        assert response.json['filename'] == 'zebra.jpg'
        assert response.json['src'] == test_src_asset
        assert src_response.status_code == 200
        assert src_response.content_type == 'image/jpeg'
        assert (
            hashlib.md5(src_response.data).hexdigest()
            == '9c2e4476488534c05b7c557a0e663ccd'
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
    clone = utils.clone_submission(
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
    admin_user,
    researcher_1,
    test_clone_submission_data,
):
    # Clone the known submission so that the asset data is in the database
    clone = utils.clone_submission(
        flask_app_client,
        researcher_1,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )

    try:
        with flask_app_client.login(admin_user, auth_scopes=('assets:read',)):
            admin_response = flask_app_client.get('/api/v1/assets/')
        with flask_app_client.login(researcher_1, auth_scopes=('assets:read',)):
            researcher_response = flask_app_client.get('/api/v1/assets/')

        assert researcher_response.status_code == 200
        assert researcher_response.content_type == 'application/json'
        assert len(researcher_response.json) == 2
        # both of these lists should be lexical order
        assert (
            researcher_response.json[0]['guid']
            == test_clone_submission_data['asset_uuids'][0]
        )
        assert (
            researcher_response.json[1]['guid']
            == test_clone_submission_data['asset_uuids'][1]
        )
        utils.validate_dict_response(admin_response, 403, {'status', 'message'})

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()
