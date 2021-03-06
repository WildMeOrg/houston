# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import uuid
from tests.utils import clone_submission


def test_ensure_submission_by_uuid(
    flask_app_client, regular_user, db, test_submission_uuid
):
    clone_submission(flask_app_client, regular_user, test_submission_uuid)


def test_ensure_empty_submission_by_uuid(
    flask_app_client, regular_user, db, test_empty_submission_uuid
):
    clone_submission(flask_app_client, regular_user, test_empty_submission_uuid)


def test_ensure_clone_submission_by_uuid(
    flask_app_client, regular_user, db, test_clone_submission_data
):
    from app.modules.submissions.models import SubmissionMajorType
    from app.modules.assets.models import Asset

    clone = clone_submission(
        flask_app_client,
        regular_user,
        test_clone_submission_data['submission_uuid'],
        later_usage=True,
    )

    try:
        assert clone.temp_submission.major_type == SubmissionMajorType.test
        assert clone.temp_submission.commit == 'e94db0cf015c6c84ab1668186924dc985fc472d6'
        assert clone.temp_submission.commit_mime_whitelist_guid == uuid.UUID(
            '4d46c55d-accf-29f1-abe7-a24839ec1b95'
        )

        assert clone.temp_submission.commit_houston_api_version == '0.1.0.8b208226'
        assert clone.temp_submission.description == 'Test Submission (streamlined)'

        # Checks that there are two valid Assets in the database
        assert len(clone.temp_submission.assets) == 2
        temp_assets = sorted(clone.temp_submission.assets)
        expected_guid_list = [
            uuid.UUID(test_clone_submission_data['asset_uuids'][0]),
            uuid.UUID(test_clone_submission_data['asset_uuids'][1]),
        ]

        for asset, expected_guid in zip(temp_assets, expected_guid_list):
            db_asset = Asset.query.get(asset.guid)
            assert asset == db_asset
            assert asset.guid == expected_guid

    except Exception as ex:
        raise ex
    finally:
        clone.cleanup()
