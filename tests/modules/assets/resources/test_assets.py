# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import hashlib
from tests.utils import clone_submission

def test_find_asset(
    flask_app_client, regular_user, admin_user, db, test_clone_submission_uuid, test_asset_uuid
):
    # Clone the known submission so that the asset data is in the database
    clone = clone_submission(flask_app_client, regular_user, test_clone_submission_uuid, later_usage=True)

    try:
        # For reasons that are not clear, you can clone as a regular user but need admin role to read the asset but not the data
        # Seems wrong to me
        with flask_app_client.login(admin_user, auth_scopes=('assets:read',)):
            response = flask_app_client.get('/api/v1/assets/%s' % test_asset_uuid)
        with flask_app_client.login(regular_user, auth_scopes=('assets:read',)):
            src_response = flask_app_client.get('/api/v1/assets/src/%s' % test_asset_uuid)

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert response.json['filename'] == 'fluke.jpg'
        assert response.json['src'] == '/api/v1/assets/src/%s' % test_asset_uuid
        assert src_response.status_code == 200
        assert src_response.content_type == 'image/jpeg'
        assert hashlib.md5(src_response.data).hexdigest() == '0b546f813ec9631ce5c9b1dd579c623b'

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()

def test_find_deleted_asset(
    flask_app_client, regular_user, admin_user, db, test_clone_submission_uuid, test_asset_uuid
):
    # Clone the known submission so that the asset data is in the database
    clone = clone_submission(flask_app_client, regular_user, test_clone_submission_uuid, later_usage=True)

    try:
        # As for the test above but now remove the files so that Houston knows about the asset but does not have the files
        clone.remove_files()

        # For reasons that are not clear, you can clone as a regular user but need admin role to read the asset but not the data
        # Seems wrong to me
        with flask_app_client.login(admin_user, auth_scopes=('assets:read',)):
            response = flask_app_client.get('/api/v1/assets/%s' % test_asset_uuid)
        with flask_app_client.login(regular_user, auth_scopes=('assets:read',)):
            src_response = flask_app_client.get('/api/v1/assets/src/%s' % test_asset_uuid)

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert response.json['filename'] == 'fluke.jpg'
        assert response.json['src'] == '/api/v1/assets/src/%s' % test_asset_uuid
        assert src_response.status_code == 200
        assert src_response.content_type == 'image/jpeg'
        assert hashlib.md5(src_response.data).hexdigest() == '0b546f813ec9631ce5c9b1dd579c623b'

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()
