# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import config
import shutil
import uuid
import os
from app.modules.submissions.models import Submission, SubmissionMajorType
from app.modules.assets.models import Asset

def test_list_all_assets():
    assets = Asset.query.all()

    for asset in assets:
        print("Asset : {} ".format(asset))


def test_get_asset_by_uuid(
    flask_app_client, regular_user, db, test_asset_uuid
):
    # pylint: disable=invalid-name
    temp_asset = None

    try:
        with flask_app_client.login(regular_user, auth_scopes=('assets:read',)):
            response = flask_app_client.get(
                '/api/v1/assets/%s' % test_asset_uuid
            )

        temp_asset = Asset.query.get(response.json['guid'])

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert isinstance(response.json, dict)
        assert set(response.json.keys()) >= {'guid', 'owner_guid', 'major_type', 'commit'}
        assert response.json.get('guid') == str(test_asset_uuid)
    except Exception as ex:
        raise ex
    finally:
        # Restore original state
        if temp_asset is not None:
            temp_asset.delete()


def test_ensure_empty_asset_by_uuid(
    flask_app_client, regular_user, db, test_empty_submission_uuid
):
    # pylint: disable=invalid-name
    temp_asset = None

    try:
        with flask_app_client.login(regular_user, auth_scopes=('assets:read',)):
            response = flask_app_client.get(
                '/api/v1/asset/%s' % test_empty_submission_uuid
            )

        temp_asset = Asset.query.get(response.json['guid'])

        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert isinstance(response.json, dict)
        assert set(response.json.keys()) >= {'guid', 'owner_guid', 'major_type', 'commit'}
        assert response.json.get('guid') == str(test_empty_submission_uuid)
    except Exception as ex:
        raise ex
    finally:
        # Restore original state
        if temp_asset is not None:
            temp_asset.delete()

